// 5+App uses the native recorder. HTTPS pages use the browser's MediaRecorder.
const webFormats = ['audio/webm;codecs=opus', 'audio/mp4', 'audio/ogg;codecs=opus']
let capturing = false

function webRecording(signal, ready) {
  if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
    throw new Error('当前环境无法录音，请用系统浏览器打开或继续打字。')
  }
  return navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1 } }).then(stream => {
    const release = () => stream.getTracks().forEach(track => track.stop())
    if (signal.aborted) {
      release()
      return null
    }

    return new Promise((resolve, reject) => {
      let recorder
      const chunks = []
      const finish = () => {
        if (recorder?.state === 'recording') recorder.stop()
      }
      const cleanup = () => {
        signal.removeEventListener('abort', cancel)
        release()
      }
      function cancel() {
        try { finish() } finally { cleanup(); resolve(null) }
      }
      try {
        const mimeType = webFormats.find(type => MediaRecorder.isTypeSupported?.(type))
        recorder = new MediaRecorder(stream, mimeType ? { mimeType, audioBitsPerSecond: 48000 } : undefined)
        recorder.ondataavailable = event => {
          if (event.data.size) chunks.push(event.data)
        }
        recorder.onstop = () => {
          cleanup()
          resolve(new Blob(chunks, { type: recorder.mimeType || chunks[0]?.type }))
        }
        recorder.onerror = () => {
          cleanup()
          reject(new Error('录音中断，请重试。'))
        }
        signal.addEventListener('abort', cancel, { once: true })
        recorder.start()
        ready(finish)
      } catch (error) {
        cleanup()
        reject(error)
      }
    })
  })
}

function removeRecording(plus, path) {
  plus.io.resolveLocalFileSystemURL(path, entry => entry.remove(() => {}, () => {}), () => {})
}

function readNativeAudio(plus, path, mime) {
  return new Promise((resolve, reject) => {
    const failed = () => reject(new Error('无法读取录音，请重试。'))
    plus.io.resolveLocalFileSystemURL(path, entry => {
      entry.file(file => {
        const reader = new plus.io.FileReader()
        reader.onload = event => {
          try {
            const dataUrl = event.target.result
            const raw = atob(dataUrl.slice(dataUrl.indexOf(',') + 1))
            resolve(new Blob([Uint8Array.from(raw, char => char.charCodeAt(0))], { type: mime }))
          } catch {
            failed()
          }
        }
        reader.onerror = failed
        reader.onabort = failed
        reader.readAsDataURL(file)
      }, failed)
    }, failed)
  })
}

function nativeRecording(plus, signal, ready) {
  return new Promise((resolve, reject) => {
    const recorder = plus.audio.getRecorder()
    if (!recorder) {
      reject(new Error('无法打开麦克风，请检查应用的麦克风权限。'))
      return
    }
    const format = plus.os?.name === 'iOS' ? 'wav' : 'amr'
    const path = `_doc/shiyang-voice-${Date.now()}.${format}`
    let stopping = false
    const finish = () => {
      if (!stopping) {
        stopping = true
        recorder.stop()
      }
    }
    const onAbort = () => {
      try { finish() } catch { removeRecording(plus, path) }
      resolve(null)
    }
    const failed = () => {
      signal.removeEventListener('abort', onAbort)
      removeRecording(plus, path)
      reject(new Error('录音失败，请检查应用的麦克风权限。'))
    }
    signal.addEventListener('abort', onAbort, { once: true })
    try {
      recorder.record({ filename: path, format }, async filePath => {
        try {
          if (!signal.aborted) resolve(await readNativeAudio(plus, filePath, `audio/${format}`))
        } catch (error) {
          reject(error)
        } finally {
          signal.removeEventListener('abort', onAbort)
          removeRecording(plus, filePath)
        }
      }, failed)
      ready(finish)
    } catch {
      failed()
    }
  })
}

export async function captureVoice(signal, ready) {
  if (capturing) throw new Error('已有一个输入框正在录音。')
  capturing = true
  try {
    const plus = window.plus
    if (plus?.audio && plus?.io) return await nativeRecording(plus, signal, ready)
    return await webRecording(signal, ready)
  } finally {
    capturing = false
  }
}
