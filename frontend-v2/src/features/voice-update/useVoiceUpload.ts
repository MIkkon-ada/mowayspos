import { useRef, useState } from 'react'
import { apiUpload } from '../../api/client'

type UseVoiceUploadArgs = {
  setText: (updater: string | ((prev: string) => string)) => void
  setError: (value: string | null) => void
}

export function useVoiceUpload({ setText, setError }: UseVoiceUploadArgs) {
  const [uploading, setUploading] = useState(false)
  const [uploadFileName, setUploadFileName] = useState('')
  const uploadInputRef = useRef<HTMLInputElement>(null)

  async function handleUploadFile(file: File) {
    setUploading(true)
    setError(null)
    setUploadFileName(file.name)
    try {
      const fd = new FormData()
      fd.append('file', file)
      const res = await apiUpload<{ text: string }>('/api/transcribe', fd)
      setText((prev) => (prev ? `${prev}\n${res.text}` : res.text))
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : '转写失败，请重试')
    } finally {
      setUploading(false)
    }
  }

  return {
    uploading,
    uploadFileName,
    uploadInputRef,
    handleUploadFile,
  }
}
