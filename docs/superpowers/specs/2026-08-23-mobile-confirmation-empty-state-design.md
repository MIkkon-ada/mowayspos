# Mobile confirmation empty-state design

## Goal

The Enterprise WeChat mobile confirmation screen must reflect Feng Hailin's real review queue. It must never fabricate a pending task card when no submission is selected.

## Behaviour

- When the filtered confirmation queue has no selected submission, the mobile screen shows only a clear `暂无待确认事项` empty state.
- The task-card stream and action controls render only after a real submission has been selected.
- Existing desktop behaviour and confirmation actions remain unchanged.

## Data flow

`ConfirmPage` owns the selected submission. It passes an empty card list to the mobile stream when that value is null; otherwise it passes the cards derived from the selected submission's persisted result.

## Verification

- A structural test asserts that the mobile props are empty when `selected` is absent.
- The targeted mobile confirmation test and production build pass.
