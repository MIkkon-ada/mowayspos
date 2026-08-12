import { useRef, useState } from 'react'

import { extractWorkReportDocumentText } from '../../api/updates'

const MAX_DOCUMENT_BYTES = 20 * 1024 * 1024

type UseVoiceDocumentUploadArgs = {
  setText: (value: string) => void
  setError: (value: string | null) => void
}

export function useVoiceDocumentUpload({ setText, setError }: UseVoiceDocumentUploadArgs) {
  const [documentUploading, setDocumentUploading] = useState(false)
  const [documentFileName, setDocumentFileName] = useState('')
  const [documentCharCount, setDocumentCharCount] = useState(0)
  const documentInputRef = useRef<HTMLInputElement>(null)

  async function handleDocumentFile(file: File) {
    if (file.size > MAX_DOCUMENT_BYTES) {
      setError('文档不能超过 20 MB')
      return
    }
    setDocumentUploading(true)
    setDocumentFileName(file.name)
    setDocumentCharCount(0)
    setError(null)
    try {
      const result = await extractWorkReportDocumentText(file)
      setText(result.text)
      setDocumentFileName(result.filename)
      setDocumentCharCount(result.char_count)
    } catch (error: unknown) {
      setDocumentFileName('')
      setDocumentCharCount(0)
      setError(error instanceof Error ? error.message : '文档解析失败，请重试')
    } finally {
      setDocumentUploading(false)
      if (documentInputRef.current) documentInputRef.current.value = ''
    }
  }

  function removeDocument() {
    setDocumentFileName('')
    setDocumentCharCount(0)
    if (documentInputRef.current) documentInputRef.current.value = ''
  }

  return {
    documentUploading,
    documentFileName,
    documentCharCount,
    documentInputRef,
    handleDocumentFile,
    removeDocument,
  }
}
