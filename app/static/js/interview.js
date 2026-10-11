// Live Interview Room Script: Timer, Auto-Save, and Transparent Integrity Logging
document.addEventListener("DOMContentLoaded", () => {
  const roomData = document.getElementById("interview-room-data");
  if (!roomData) return;

  const sessionId = roomData.dataset.sessionId;
  const questionId = roomData.dataset.questionId;
  const timeLimit = parseInt(roomData.dataset.timeLimit, 10) || 120;
  const csrfToken = roomData.dataset.csrfToken || "";

  const timerEl = document.getElementById("timer-display");
  const answerInput = document.getElementById("answer-textarea");
  const answerForm = document.getElementById("interview-answer-form");
  const durationInput = document.getElementById("duration-seconds-input");
  const isTimeoutInput = document.getElementById("is-timeout-input");
  const submitBtn = document.getElementById("submit-answer-btn");

  let secondsRemaining = timeLimit;
  let secondsElapsed = 0;
  let submitted = false;

  // Restore draft from localStorage if available
  const draftKey = `interview_draft_${sessionId}_${questionId}`;
  if (answerInput) {
    const savedDraft = localStorage.getItem(draftKey);
    if (savedDraft && !answerInput.value) {
      answerInput.value = savedDraft;
    }

    // Auto-save on input
    answerInput.addEventListener("input", () => {
      localStorage.setItem(draftKey, answerInput.value);
    });
  }

  // Update timer display
  function updateTimer() {
    const mins = Math.floor(secondsRemaining / 60);
    const secs = secondsRemaining % 60;
    if (timerEl) {
      timerEl.textContent = `${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
      if (secondsRemaining <= 20) {
        timerEl.style.color = "#dc2626";
        timerEl.style.fontWeight = "700";
      }
    }

    if (secondsRemaining <= 0) {
      clearInterval(timerInterval);
      handleTimeout();
    } else {
      secondsRemaining--;
      secondsElapsed++;
    }
  }

  const timerInterval = setInterval(updateTimer, 1000);
  updateTimer();

  function handleTimeout() {
    if (submitted) return;
    submitted = true;
    stopVoiceFeatures();
    if (isTimeoutInput) isTimeoutInput.value = "true";
    if (durationInput) durationInput.value = secondsElapsed;
    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.textContent = "Time expired — Submitting...";
    }
    localStorage.removeItem(draftKey);
    answerForm.submit();
  }

  if (answerForm) {
    answerForm.addEventListener("submit", (e) => {
      if (submitted) {
        e.preventDefault();
        return;
      }
      submitted = true;
      stopVoiceFeatures();
      if (durationInput) durationInput.value = secondsElapsed;
      if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.textContent = "Evaluating Answer...";
      }
      localStorage.removeItem(draftKey);
    });
  }


  // ==========================================
  // Voice support: spoken questions + speech-to-text answers
  // Uses built-in browser APIs; typed answers remain available as a fallback.
  // ==========================================
  const questionTextEl = document.getElementById("interview-question-text");
  const speakQuestionBtn = document.getElementById("speak-question-btn");
  const stopSpeechBtn = document.getElementById("stop-speech-btn");
  const playbackStatus = document.getElementById("speech-playback-status");
  const startRecordingBtn = document.getElementById("start-recording-btn");
  const stopRecordingBtn = document.getElementById("stop-recording-btn");
  const clearVoiceBtn = document.getElementById("clear-voice-btn");
  const recordingStatus = document.getElementById("voice-recording-status");
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  let recognition = null;
  let recordingBaseText = "";
  let voiceRecognitionActive = false;

  // Browser voices vary by OS/browser. Prefer voices commonly presented as
  // feminine, while keeping a locale-matched fallback if none is available.
  function getPreferredQuestionVoice() {
    if (!("speechSynthesis" in window)) return null;
    const voices = window.speechSynthesis.getVoices() || [];
    if (!voices.length) return null;

    const feminineHints = [
      "female", "samantha", "ava", "jenny", "aria", "zira", "susan",
      "karen", "moira", "tessa", "victoria", "serena", "google uk english female",
      "google us english", "veena", "heera", "priya"
    ];
    const englishVoices = voices.filter((voice) => /^en([_-]|$)/i.test(voice.lang || ""));
    const candidates = englishVoices.length ? englishVoices : voices;
    const score = (voice) => {
      const name = (voice.name || "").toLowerCase();
      const lang = (voice.lang || "").toLowerCase();
      let value = 0;
      if (feminineHints.some((hint) => name.includes(hint))) value += 10;
      if (/en[-_]in/i.test(lang)) value += 4;
      else if (/en[-_]gb/i.test(lang)) value += 3;
      else if (/en[-_]us/i.test(lang)) value += 2;
      if (voice.gender && String(voice.gender).toLowerCase() === "female") value += 10;
      return value;
    };
    return candidates.slice().sort((a, b) => score(b) - score(a))[0] || null;
  }

  function stopQuestionSpeech() {
    if ("speechSynthesis" in window) window.speechSynthesis.cancel();
    if (stopSpeechBtn) stopSpeechBtn.disabled = true;
    if (speakQuestionBtn) speakQuestionBtn.disabled = false;
    if (playbackStatus) playbackStatus.textContent = "Audio stopped.";
  }

  if ("speechSynthesis" in window) {
    // Some browsers populate the voice list asynchronously.
    window.speechSynthesis.getVoices();
    window.speechSynthesis.addEventListener?.("voiceschanged", () => {
      window.speechSynthesis.getVoices();
    });
  }

  if (speakQuestionBtn) {
    speakQuestionBtn.addEventListener("click", () => {
      if (!("speechSynthesis" in window) || !questionTextEl) {
        if (playbackStatus) playbackStatus.textContent = "Voice playback is not supported in this browser. Please read the question on screen.";
        return;
      }
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(questionTextEl.textContent.trim());
      utterance.lang = "en-IN";
      utterance.rate = 0.95;
      const preferredVoice = getPreferredQuestionVoice();
      if (preferredVoice) {
        utterance.voice = preferredVoice;
        utterance.lang = preferredVoice.lang || "en-IN";
        if (playbackStatus) playbackStatus.textContent = `Using ${preferredVoice.name} voice…`;
      } else if (playbackStatus) {
        playbackStatus.textContent = "Using your browser's default voice; no preferred voice is currently available.";
      }
      utterance.onstart = () => {
        if (playbackStatus && !preferredVoice) playbackStatus.textContent = "Reading the question aloud…";
        speakQuestionBtn.disabled = true;
        if (stopSpeechBtn) stopSpeechBtn.disabled = false;
      };
      utterance.onend = () => {
        if (playbackStatus) playbackStatus.textContent = "Question audio finished.";
        speakQuestionBtn.disabled = false;
        if (stopSpeechBtn) stopSpeechBtn.disabled = true;
      };
      utterance.onerror = () => {
        if (playbackStatus) playbackStatus.textContent = "Could not play audio. You can still read the question.";
        speakQuestionBtn.disabled = false;
        if (stopSpeechBtn) stopSpeechBtn.disabled = true;
      };
      window.speechSynthesis.speak(utterance);
    });
  }
  if (stopSpeechBtn) stopSpeechBtn.addEventListener("click", stopQuestionSpeech);

  if (SpeechRecognition && startRecordingBtn && stopRecordingBtn && answerInput) {
    recognition = new SpeechRecognition();
    recognition.lang = "en-IN";
    recognition.continuous = true;
    recognition.interimResults = true;

    recognition.onstart = () => {
      voiceRecognitionActive = true;
      startRecordingBtn.disabled = true;
      stopRecordingBtn.disabled = false;
      if (recordingStatus) recordingStatus.textContent = "Listening… Speak clearly. Select Stop recording when you finish.";
    };

    recognition.onresult = (event) => {
      let finalTranscript = "";
      let interimTranscript = "";
      for (let i = 0; i < event.results.length; i++) {
        const phrase = event.results[i][0].transcript;
        if (event.results[i].isFinal) finalTranscript += phrase + " ";
        else interimTranscript += phrase;
      }
      const base = recordingBaseText.trim();
      const recognized = (finalTranscript + interimTranscript).trim();
      answerInput.value = [base, recognized].filter(Boolean).join(base && recognized ? "\n\n" : "");
      answerInput.dispatchEvent(new Event("input", { bubbles: true }));
    };

    recognition.onerror = (event) => {
      const messages = {
        "not-allowed": "Microphone permission was denied. Allow microphone access in your browser settings, or type your answer.",
        "no-speech": "No speech was detected. Try again closer to your microphone.",
        "audio-capture": "No microphone was found. Connect a microphone or type your answer.",
        "network": "Browser speech recognition needs a network connection. You can type your answer instead."
      };
      if (recordingStatus) recordingStatus.textContent = messages[event.error] || `Speech recognition error (${event.error}). You can type your answer instead.`;
    };

    recognition.onend = () => {
      voiceRecognitionActive = false;
      startRecordingBtn.disabled = submitted;
      stopRecordingBtn.disabled = true;
      if (recordingStatus && !submitted && !recordingStatus.textContent.includes("permission was denied") && !recordingStatus.textContent.includes("No microphone")) {
        recordingStatus.textContent = "Recording stopped. Review or edit the transcript before submitting.";
      }
    };

    startRecordingBtn.addEventListener("click", () => {
      if (submitted || voiceRecognitionActive) return;
      recordingBaseText = answerInput.value;
      if (recordingStatus) recordingStatus.textContent = "Requesting microphone access…";
      try { recognition.start(); }
      catch (error) {
        if (recordingStatus) recordingStatus.textContent = "Voice input could not start. If it is already listening, press Stop recording; otherwise reload and try again.";
      }
    });

    stopRecordingBtn.addEventListener("click", () => {
      if (recognition && voiceRecognitionActive) recognition.stop();
    });
  } else {
    if (startRecordingBtn) startRecordingBtn.disabled = true;
    if (stopRecordingBtn) stopRecordingBtn.disabled = true;
    if (recordingStatus) recordingStatus.textContent = "Speech recognition is not supported by this browser. Try a supported desktop browser or type your answer.";
  }

  if (clearVoiceBtn && answerInput) {
    clearVoiceBtn.addEventListener("click", () => {
      answerInput.value = "";
      answerInput.dispatchEvent(new Event("input", { bubbles: true }));
      if (recordingStatus) recordingStatus.textContent = "Answer cleared. You can type or record a new answer.";
      answerInput.focus();
    });
  }

  function stopVoiceFeatures() {
    if (recognition && voiceRecognitionActive) {
      try { recognition.stop(); } catch (_) { /* already stopped */ }
    }
    if ("speechSynthesis" in window) window.speechSynthesis.cancel();
  }

  // ==========================================
  // Transparent Integrity Event Logging
  // ==========================================
  function sendIntegrityEvent(eventType, context) {
    if (submitted) return;
    try {
      fetch("/integrity/log-event", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrfToken,
        },
        body: JSON.stringify({
          session_id: sessionId,
          question_id: questionId,
          event_type: eventType,
          context: context,
        }),
      }).catch((err) => console.debug("Integrity log note:", err));
    } catch (e) {
      // Non-blocking
    }
  }

  // 1. Tab / Visibility State Change
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "hidden") {
      sendIntegrityEvent("visibility_hidden", "Browser tab/window hidden or switched during active question.");
    }
  });

  // 2. Window Blur (Focus Lost)
  window.addEventListener("blur", () => {
    sendIntegrityEvent("window_blur", "Interview browser window lost focus.");
  });

  // 3. Prevent accidental navigation
  window.addEventListener("beforeunload", (e) => {
    if (!submitted) {
      sendIntegrityEvent("navigation_attempt", "Candidate attempted to leave active interview room.");
    }
  });
});
