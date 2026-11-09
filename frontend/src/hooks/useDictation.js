import { useCallback, useRef, useState } from 'react';
import api, { errorMessage } from '../api';

// Same one-take dictation as the hospital OPD: record one clip, show a live
// caption while talking, then /api/dictate transcribes it and returns
// AI-structured fields to pre-fill the visit.
const PREVIEW_INTERVAL_MS = 4000;
const PREVIEW_MIN_CHUNKS = 5;

export function useDictation({ onResult, onError }) {
  const [isRecording, setIsRecording] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [caption, setCaption] = useState('');
  const [language, setLanguage] = useState(null);

  const recorderRef = useRef(null);
  const chunksRef = useRef([]);
  const timerRef = useRef(null);
  const previewTimerRef = useRef(null);
  const previewBusyRef = useRef(false);
  const cancelledRef = useRef(false);
  const abortRef = useRef(null);
  const languageRef = useRef(null);
  const audioCtxRef = useRef(null);
  const analyserRef = useRef(null);
  const handlersRef = useRef({ onResult, onError });
  handlersRef.current = { onResult, onError };

  const ext = (mime) => (mime.includes('ogg') ? '.ogg' : '.webm');

  const sendPreview = useCallback(async (mime) => {
    if (previewBusyRef.current || chunksRef.current.length < PREVIEW_MIN_CHUNKS) return;
    previewBusyRef.current = true;
    try {
      const form = new FormData();
      form.append('audio', new Blob(chunksRef.current, { type: mime }), `preview${ext(mime)}`);
      form.append('language', languageRef.current || '');
      const { data } = await api.post('/api/transcribe/preview', form);
      if (data?.text) setCaption(data.text);
      if (!languageRef.current && data?.language) {
        languageRef.current = data.language;
        setLanguage(data.language);
      }
    } catch {
      /* caption just skips a beat */
    } finally {
      previewBusyRef.current = false;
    }
  }, []);

  const teardown = () => {
    analyserRef.current = null;
    const ctx = audioCtxRef.current;
    audioCtxRef.current = null;
    if (ctx && ctx.state !== 'closed') ctx.close().catch(() => {});
  };

  const sendAudio = async (blob, mime) => {
    const controller = new AbortController();
    abortRef.current = controller;
    try {
      const form = new FormData();
      form.append('audio', blob, `dictation${ext(mime)}`);
      form.append('language', languageRef.current || '');
      const { data } = await api.post('/api/dictate', form, { signal: controller.signal, timeout: 180000 });
      handlersRef.current.onResult(data);
    } catch (err) {
      if (err.code === 'ERR_CANCELED') return;
      handlersRef.current.onError(errorMessage(err, 'Dictation processing failed'));
    } finally {
      setIsProcessing(false);
      setElapsed(0);
    }
  };

  const start = useCallback(async () => {
    let stream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      handlersRef.current.onError(
        window.isSecureContext ? 'Microphone access denied. Please allow the microphone.' : 'The microphone only works on https:// or localhost.',
      );
      return;
    }
    const mime = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
      ? 'audio/webm;codecs=opus'
      : MediaRecorder.isTypeSupported('audio/ogg;codecs=opus') ? 'audio/ogg;codecs=opus' : 'audio/webm';
    const recorder = new MediaRecorder(stream, { mimeType: mime });
    recorderRef.current = recorder;
    chunksRef.current = [];
    cancelledRef.current = false;
    languageRef.current = null;
    setLanguage(null);
    setCaption('');

    const Ctx = window.AudioContext || window.webkitAudioContext;
    const ctx = new Ctx();
    const analyser = ctx.createAnalyser();
    analyser.fftSize = 128;
    analyser.smoothingTimeConstant = 0.7;
    ctx.createMediaStreamSource(stream).connect(analyser);
    audioCtxRef.current = ctx;
    analyserRef.current = analyser;

    recorder.ondataavailable = (e) => { if (e.data.size > 0) chunksRef.current.push(e.data); };
    recorder.onstop = async () => {
      teardown();
      stream.getTracks().forEach((t) => t.stop());
      if (cancelledRef.current) return;
      await sendAudio(new Blob(chunksRef.current, { type: mime }), mime);
    };

    recorder.start(100);
    setIsRecording(true);
    setElapsed(0);
    timerRef.current = setInterval(() => setElapsed((s) => s + 1), 1000);
    previewTimerRef.current = setInterval(() => sendPreview(mime), PREVIEW_INTERVAL_MS);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sendPreview]);

  const stop = useCallback(() => {
    if (!recorderRef.current || !isRecording) return;
    clearInterval(timerRef.current);
    clearInterval(previewTimerRef.current);
    setIsRecording(false);
    setIsProcessing(true);
    recorderRef.current.stop();
  }, [isRecording]);

  const cancel = useCallback(() => {
    if (isRecording) {
      cancelledRef.current = true;
      clearInterval(timerRef.current);
      clearInterval(previewTimerRef.current);
      setIsRecording(false);
      recorderRef.current?.stop();
      setElapsed(0);
      setCaption('');
    } else if (isProcessing) {
      abortRef.current?.abort();
    }
  }, [isRecording, isProcessing]);

  return { isRecording, isProcessing, elapsed, caption, language, analyserRef, start, stop, cancel };
}
