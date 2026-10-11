import { useCallback, useEffect, useRef, useState } from 'react'
import { eventsUrl } from '../api'
import { isFailedState } from '../constants'

// Subscribe to the backend SSE job stream for a project.
//
// The stream emits `{stage, state, done, total, message}`. We surface the
// latest event as `progress`, and settle (closing the stream + firing a
// callback) when the state reaches the stage's success or failure terminal.
//
//   const { progress, running, start, stop } = useJobEvents()
//   start(projectId, {
//     terminals: JOB_TERMINALS.draft,   // {success, failure}
//     onDone: (finalEvent) => {...},
//     onError: (err, finalEvent) => {...},
//   })
export function useJobEvents() {
  const [progress, setProgress] = useState(null)
  const [running, setRunning] = useState(false)
  const esRef = useRef(null)
  const cbRef = useRef({})

  const stop = useCallback(() => {
    if (esRef.current) {
      esRef.current.close()
      esRef.current = null
    }
    setRunning(false)
  }, [])

  const start = useCallback(
    (id, { terminals, onDone, onError } = {}) => {
      stop()
      setProgress(null)
      setRunning(true)
      cbRef.current = { terminals, onDone, onError }

      const es = new EventSource(eventsUrl(id))
      esRef.current = es

      es.onmessage = (evt) => {
        let data
        try {
          data = JSON.parse(evt.data)
        } catch {
          return
        }
        setProgress(data)

        const { terminals: t, onDone: done, onError: fail } = cbRef.current
        const state = data.state
        if (isFailedState(state) || (t && state === t.failure)) {
          stop()
          fail?.(new Error(data.message || 'The job failed.'), data)
        } else if (t && state === t.success) {
          stop()
          done?.(data)
        }
      }

      es.onerror = () => {
        // The stream closes normally when a job finishes; only treat it as an
        // error if we were still expecting more events.
        if (esRef.current) {
          stop()
          cbRef.current.onError?.(
            new Error('Lost connection to the job stream.'),
            null
          )
        }
      }
    },
    [stop]
  )

  useEffect(() => stop, [stop])

  return { progress, running, start, stop }
}
