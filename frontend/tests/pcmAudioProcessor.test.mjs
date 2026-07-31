import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import vm from "node:vm";
import { fileURLToPath } from "node:url";

const testDirectory = path.dirname(fileURLToPath(import.meta.url));
const workletPath = path.resolve(
  testDirectory,
  "../public/worklets/pcm-audio-processor.js",
);
const workletSource = fs.readFileSync(workletPath, "utf8");

function createProcessor() {
  let ProcessorClass;

  class FakeAudioWorkletProcessor {
    constructor() {
      this.port = {
        messages: [],
        onmessage: null,
        postMessage: (message, transfer = []) => {
          this.port.messages.push({ message, transfer });
        },
      };
    }
  }

  vm.runInNewContext(workletSource, {
    AudioWorkletProcessor: FakeAudioWorkletProcessor,
    Float32Array,
    Int16Array,
    Math,
    registerProcessor: (name, implementation) => {
      assert.equal(name, "pcm-audio-processor");
      ProcessorClass = implementation;
    },
  });

  assert.ok(ProcessorClass, "worklet should register its processor");
  return new ProcessorClass();
}

function processSamples(processor, samples) {
  return processor.process([[Float32Array.from(samples)]]);
}

function messagesOfType(processor, type) {
  return processor.port.messages
    .map(({ message }) => message)
    .filter((message) => message.type === type);
}

test("accumulates arbitrary render quanta into one 100ms PCM packet", () => {
  const processor = createProcessor();

  for (let index = 0; index < 12; index += 1) {
    assert.equal(processSamples(processor, new Float32Array(128)), true);
  }
  assert.equal(processSamples(processor, new Float32Array(64)), true);

  const pcmMessages = messagesOfType(processor, "pcm");
  assert.equal(pcmMessages.length, 1);
  assert.equal(pcmMessages[0].buffer.byteLength, 3200);
  assert.equal(processor.port.messages[0].transfer.length, 1);
  assert.equal(processor.port.messages[0].transfer[0], pcmMessages[0].buffer);
});

test("emits multiple full packets from one large input and retains the remainder", () => {
  const processor = createProcessor();

  assert.equal(processSamples(processor, new Float32Array(3300)), true);

  let pcmMessages = messagesOfType(processor, "pcm");
  assert.deepEqual(
    pcmMessages.map(({ buffer }) => buffer.byteLength),
    [3200, 3200],
  );

  processor.port.onmessage({ data: { type: "stop" } });

  pcmMessages = messagesOfType(processor, "pcm");
  assert.deepEqual(
    pcmMessages.map(({ buffer }) => buffer.byteLength),
    [3200, 3200, 200],
  );
});

test("stop flushes a short remainder and acknowledges exactly once", () => {
  const processor = createProcessor();

  processSamples(processor, new Float32Array(128));
  processor.port.onmessage({ data: { type: "stop" } });
  processor.port.onmessage({ data: { type: "stop" } });

  const pcmMessages = messagesOfType(processor, "pcm");
  assert.equal(pcmMessages.length, 1);
  assert.equal(pcmMessages[0].buffer.byteLength, 256);
  assert.equal(messagesOfType(processor, "flushed").length, 1);
});

test("stop after an exact packet acknowledges without emitting empty PCM", () => {
  const processor = createProcessor();

  processSamples(processor, new Float32Array(1600));
  processor.port.onmessage({ data: { type: "stop" } });

  assert.equal(messagesOfType(processor, "pcm").length, 1);
  assert.equal(messagesOfType(processor, "flushed").length, 1);
});

test("process stops permanently after stop and produces no further output", () => {
  const processor = createProcessor();

  processSamples(processor, new Float32Array(64));
  processor.port.onmessage({ data: { type: "stop" } });
  const messageCountAfterStop = processor.port.messages.length;

  assert.equal(processSamples(processor, new Float32Array(1600)), false);
  assert.equal(processor.port.messages.length, messageCountAfterStop);
});

test("clamps Float32 samples while preserving signed Int16 conversion", () => {
  const processor = createProcessor();

  processSamples(processor, [1, -1, 2, -2, 0.5, -0.5]);
  processor.port.onmessage({ data: { type: "stop" } });

  const [pcmMessage] = messagesOfType(processor, "pcm");
  assert.deepEqual(
    Array.from(new Int16Array(pcmMessage.buffer)),
    [32767, -32768, 32767, -32768, 16383, -16384],
  );
});

test("silence is packetized and never discarded or used to stop processing", () => {
  const processor = createProcessor();

  for (let index = 0; index < 13; index += 1) {
    assert.equal(processSamples(processor, new Float32Array(128)), true);
  }

  const pcmMessages = messagesOfType(processor, "pcm");
  assert.equal(pcmMessages.length, 1);
  assert.equal(pcmMessages[0].buffer.byteLength, 3200);
});

test("empty inputs are safe and keep the worklet alive before stop", () => {
  const processor = createProcessor();

  assert.equal(processor.process([]), true);
  assert.equal(processor.process([[]]), true);
  assert.equal(processSamples(processor, []), true);
  assert.equal(processor.port.messages.length, 0);
});
