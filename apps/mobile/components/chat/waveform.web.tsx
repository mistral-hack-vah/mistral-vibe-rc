import { useEffect, useRef, useState } from 'react';
import { LiveAudioVisualizer } from 'react-audio-visualize';

type Props = { isRecording: boolean };

export function Waveform({ isRecording }: Props) {
  const [mediaRecorder, setMediaRecorder] = useState<MediaRecorder>();
  const streamRef = useRef<MediaStream>();

  useEffect(() => {
    if (isRecording) {
      navigator.mediaDevices.getUserMedia({ audio: true }).then((stream) => {
        streamRef.current = stream;
        const recorder = new MediaRecorder(stream);
        recorder.start();
        setMediaRecorder(recorder);
      });
    } else {
      mediaRecorder?.stop();
      streamRef.current?.getTracks().forEach((t) => t.stop());
      setMediaRecorder(undefined);
    }
  }, [isRecording]);

  return (
    <div style={{ height: 64 }}>
      {mediaRecorder && (
        <LiveAudioVisualizer
          mediaRecorder={mediaRecorder}
          width={300}
          height={64}
        />
      )}
    </div>
  );
}
