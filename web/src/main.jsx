import React, {
  useEffect,
  useMemo,
  useState
} from "react";

import {
  createRoot
} from "react-dom/client";

import "./styles.css";
import NotesWorkflow from "./NotesWorkflow";


const API = "/api/v1";


async function api(
  path,
  options = {}
) {
  const response = await fetch(
    path,
    {
      ...options,
      headers: {
        "Content-Type":
          "application/json",
        ...(options.headers || {})
      }
    }
  );

  let data = null;

  try {
    data = await response.json();
  } catch {
    data = null;
  }

  if (!response.ok) {
    const error = new Error(
      data?.error?.message
      || `Request failed: ${response.status}`
    );

    error.status = response.status;
    error.code = (
      data?.error?.code
      || null
    );

    error.retryAfter = (
      response.headers.get(
        "Retry-After"
      )
    );

    throw error;
  }

  return data;
}


async function waitForJob(
  path,
  {
    interval = 2500,
    timeout = 15 * 60 * 1000
  } = {}
) {
  const started = Date.now();

  while (
    Date.now() - started
    < timeout
  ) {
    let job = null;

    try {
      job = await api(path);

    } catch (err) {
      const temporary = (
        err?.status === 429
        || err?.status === 503
        || err?.code
           === "RATE_LIMITER_UNAVAILABLE"
      );

      if (!temporary) {
        throw err;
      }

      const retrySeconds = Math.max(
        1,
        Number(
          err?.retryAfter
          || 1
        )
      );

      await new Promise(
        resolve => setTimeout(
          resolve,
          Math.min(
            retrySeconds * 1000,
            5000
          )
        )
      );

      continue;
    }

    if (
      job.status === "completed"
    ) {
      return job;
    }

    if (
      job.status === "failed"
    ) {
      throw new Error(
        job.failure_reason
        || job.error_message
        || "Background job failed."
      );
    }

    await new Promise(
      resolve => setTimeout(
        resolve,
        interval
      )
    );
  }

  throw new Error(
    "Timed out waiting for the background job."
  );
}


function formatSeconds(
  value
) {
  const seconds = Number(
    value || 0
  );

  const minutes = Math.floor(
    seconds / 60
  );

  const remainder = Math.floor(
    seconds % 60
  );

  return (
    `${minutes}:`
    + String(
      remainder
    ).padStart(2, "0")
  );
}


function formatTimestamp(
  value
) {
  const total = Number(
    value || 0
  );

  const minutes = Math.floor(
    total / 60
  );

  const seconds = (
    total
    - minutes * 60
  );

  return (
    `${minutes}:`
    + seconds
      .toFixed(2)
      .padStart(5, "0")
  );
}


function App() {
  const [
    videos,
    setVideos
  ] = useState([]);

  const [
    videoId,
    setVideoId
  ] = useState("");

  const [
    step,
    setStep
  ] = useState(0);

  const [
    workflow,
    setWorkflow
  ] = useState(
    "automatic"
  );

  const [
    targetMinutes,
    setTargetMinutes
  ] = useState(5);


  const [
    noteStyle,
    setNoteStyle
  ] = useState(
    "standard"
  );

  const [
    transcript,
    setTranscript
  ] = useState(null);

  const [
    words,
    setWords
  ] = useState([]);

  const [
    summary,
    setSummary
  ] = useState(null);

  const [
    selection,
    setSelection
  ] = useState(null);

  const [
    selectedIds,
    setSelectedIds
  ] = useState([]);

  const [
    wordRanges,
    setWordRanges
  ] = useState([]);

  const [
    savedWordRanges,
    setSavedWordRanges
  ] = useState([]);

  const [
    wordStart,
    setWordStart
  ] = useState(null);

  const [
    wordEnd,
    setWordEnd
  ] = useState(null);

  const [
    render,
    setRender
  ] = useState(null);

  const [
    result,
    setResult
  ] = useState(null);

  const [
    introAsset,
    setIntroAsset
  ] = useState(null);

  const [
    outroAsset,
    setOutroAsset
  ] = useState(null);

  const [
    busy,
    setBusy
  ] = useState(false);

  const [
    activity,
    setActivity
  ] = useState("");

  const [
    error,
    setError
  ] = useState("");

  const [
    showSelectedOnly,
    setShowSelectedOnly
  ] = useState(false);

  const [
    dragMode,
    setDragMode
  ] = useState(null);


  useEffect(() => {
    loadVideos();
  }, []);

  useEffect(() => {
    const finishDrag = () => {
      setDragMode(null);
    };

    window.addEventListener(
      "pointerup",
      finishDrag
    );

    window.addEventListener(
      "pointercancel",
      finishDrag
    );

    return () => {
      window.removeEventListener(
        "pointerup",
        finishDrag
      );

      window.removeEventListener(
        "pointercancel",
        finishDrag
      );
    };
  }, []);


  async function loadVideos() {
    setError("");

    try {
      const data = await api(
        `${API}/videos`
      );

      setVideos(
        data.items || []
      );

      if (
        data.items?.length
        && !videoId
      ) {
        setVideoId(
          data.items[0].id
        );
      }

    } catch (err) {
      setError(err.message);
    }
  }


  const currentVideo = (
    videos.find(
      item => item.id === videoId
    )
  );


  const summaryBySegment = useMemo(
    () => {
      const result = new Map();

      for (
        const item
        of summary?.selections || []
      ) {
        result.set(
          Number(item.id),
          item
        );
      }

      return result;
    },
    [summary]
  );


  const wordById = useMemo(
    () => {
      const result = new Map();

      for (const word of words) {
        result.set(
          Number(word.id),
          word
        );
      }

      return result;
    },
    [words]
  );


  const wordGroups = useMemo(
    () => {
      const segments = (
        transcript?.segments || []
      );

      return segments
        .map(segment => {
          const start = Number(
            segment.start
          );

          const end = Number(
            segment.end
          );

          const segmentWords = (
            words.filter(word => {
              const wordStartTime =
                Number(word.start);

              const wordEndTime =
                Number(word.end);

              return (
                wordStartTime
                  >= start - 0.15
                &&
                wordEndTime
                  <= end + 0.15
              );
            })
          );

          return {
            segment,
            words: segmentWords
          };
        })
        .filter(
          item =>
            item.words.length > 0
        );
    },
    [
      transcript,
      words
    ]
  );


  function rangeDetails(
    startId,
    endId
  ) {
    const start = Math.min(
      Number(startId),
      Number(endId)
    );

    const end = Math.max(
      Number(startId),
      Number(endId)
    );

    const startWord = (
      wordById.get(start)
    );

    const endWord = (
      wordById.get(end)
    );

    if (
      !startWord
      || !endWord
    ) {
      return null;
    }

    const selectedWords = (
      words.filter(word => {
        const id = Number(
          word.id
        );

        return (
          id >= start
          && id <= end
        );
      })
    );

    const startTime = Number(
      startWord.start
    );

    const endTime = Number(
      endWord.end
    );

    return {
      start,
      end,
      startTime,
      endTime,
      duration:
        Math.max(
          0,
          endTime - startTime
        ),
      text:
        selectedWords
          .map(
            word => word.text
          )
          .join(" "),

      words:
        selectedWords
    };
  }


  const displayedSegments = useMemo(
    () => {
      const segments = (
        transcript?.segments || []
      );

      if (!showSelectedOnly) {
        return segments;
      }

      const chosen = new Set(
        selectedIds.map(Number)
      );

      return segments.filter(
        segment =>
          chosen.has(
            Number(segment.id)
          )
      );
    },
    [
      transcript,
      selectedIds,
      showSelectedOnly
    ]
  );


  async function prepareWorkflow() {
    if (!videoId) {
      setError(
        "Select a source video first."
      );

      return;
    }

    setBusy(true);
    setError("");
    setSummary(null);
    setSelection(null);
    setTranscript(null);
    setWords([]);
    setRender(null);
    setResult(null);

    try {
      setActivity(
        "Starting transcription..."
      );

      let transcription = await api(
        `${API}/transcriptions`,
        {
          method: "POST",
          body: JSON.stringify({
            video_id: videoId
          })
        }
      );

      if (
        transcription.status
        !== "completed"
      ) {
        if (!transcription.id) {
          throw new Error(
            "Transcription job ID is missing."
          );
        }

        setActivity(
          "Transcribing source video..."
        );

        transcription = (
          await waitForJob(
            `${API}/transcriptions/${transcription.id}`
          )
        );
      }

      setActivity(
        "Loading transcript..."
      );

      const [
        transcriptData,
        wordsData
      ] = await Promise.all([
        api(
          `${API}/videos/${videoId}/transcript`
        ),
        api(
          `${API}/videos/${videoId}/transcript/words`
        )
      ]);

      setTranscript(
        transcriptData
      );

      setWords(
        wordsData.words || []
      );

      let summaryData = null;

      if (
        workflow === "automatic"
      ) {
        setActivity(
          "Creating automatic summary..."
        );

        summaryData = await api(
          `${API}/summaries`,
          {
            method: "POST",
            body: JSON.stringify({
              video_id: videoId,
              target_minutes:
                Number(
                  targetMinutes
                )
            })
          }
        );

        if (
          summaryData.status
          !== "completed"
        ) {
          setActivity(
            "AI is selecting the highest-value learning moments..."
          );

          summaryData = (
            await waitForJob(
              `${API}/summaries/${summaryData.id}`
            )
          );
        }

        setSummary(
          summaryData
        );
      }

      setActivity(
        "Creating review draft..."
      );

      const selectionData = await api(
        `${API}/selections`,
        {
          method: "POST",
          body: JSON.stringify({
            video_id: videoId,
            summary_id:
              summaryData?.id
              || null
          })
        }
      );

      setSelection(
        selectionData
      );

      setSelectedIds(
        selectionData
          .selected_segment_ids
        || []
      );

      const initialWordRanges = (
        selectionData.word_ranges
        || []
      );

      setWordRanges(
        initialWordRanges
      );

      setSavedWordRanges(
        initialWordRanges
      );

      setStep(2);
      setActivity("");

    } catch (err) {
      setError(err.message);
      setActivity("");

    } finally {
      setBusy(false);
    }
  }


  function toggleSegment(
    segmentId
  ) {
    if (
      selection?.status
      !== "draft"
    ) {
      return;
    }

    const id = Number(
      segmentId
    );

    setSelectedIds(
      current => (
        current.includes(id)
        ? current.filter(
            item => item !== id
          )
        : [
            ...current,
            id
          ]
      )
    );
  }


  function chooseWord(
    wordId
  ) {
    if (
      selection?.status
      !== "draft"
    ) {
      return;
    }

    const id = Number(wordId);

    if (
      wordStart === null
      || (
        wordStart !== null
        && wordEnd !== null
      )
    ) {
      setWordStart(id);
      setWordEnd(null);
      return;
    }

    setWordEnd(id);
  }


  function addWordRange() {
    if (
      wordStart === null
      || wordEnd === null
    ) {
      return;
    }

    const start = Math.min(
      wordStart,
      wordEnd
    );

    const end = Math.max(
      wordStart,
      wordEnd
    );

    const duplicate = (
      wordRanges.some(
        range =>
          Number(
            range.start_word_id
          ) === start
          &&
          Number(
            range.end_word_id
          ) === end
      )
    );

    if (!duplicate) {
      setWordRanges(
        current => [
          ...current,
          {
            start_word_id: start,
            end_word_id: end
          }
        ]
      );
    }

    setWordStart(null);
    setWordEnd(null);
  }


  function clearWordSelection() {
    setWordStart(null);
    setWordEnd(null);
  }


  function selectSentenceWords(
    sentenceWords
  ) {
    if (
      !sentenceWords.length
      || selection?.status
         !== "draft"
    ) {
      return;
    }

    setWordStart(
      Number(
        sentenceWords[0].id
      )
    );

    setWordEnd(
      Number(
        sentenceWords[
          sentenceWords.length - 1
        ].id
      )
    );
  }


  function sameRange(
    left,
    right
  ) {
    return (
      Number(
        left.start_word_id
      )
      ===
      Number(
        right.start_word_id
      )
      &&
      Number(
        left.end_word_id
      )
      ===
      Number(
        right.end_word_id
      )
    );
  }


  function rangesToWordSet(
    ranges
  ) {
    const result = new Set();

    for (const range of ranges) {
      const start = Math.min(
        Number(
          range.start_word_id
        ),
        Number(
          range.end_word_id
        )
      );

      const end = Math.max(
        Number(
          range.start_word_id
        ),
        Number(
          range.end_word_id
        )
      );

      for (
        let id = start;
        id <= end;
        id += 1
      ) {
        result.add(id);
      }
    }

    return result;
  }


  function wordSetToRanges(
    wordSet
  ) {
    const ids = (
      [...wordSet]
        .map(Number)
        .sort(
          (a, b) => a - b
        )
    );

    if (!ids.length) {
      return [];
    }

    const ranges = [];

    let start = ids[0];
    let previous = ids[0];

    for (
      let index = 1;
      index < ids.length;
      index += 1
    ) {
      const current = ids[index];

      if (
        current === previous + 1
      ) {
        previous = current;
        continue;
      }

      ranges.push({
        start_word_id: start,
        end_word_id: previous
      });

      start = current;
      previous = current;
    }

    ranges.push({
      start_word_id: start,
      end_word_id: previous
    });

    return ranges;
  }


  const selectedWordIds = useMemo(
    () =>
      rangesToWordSet(
        wordRanges
      ),
    [wordRanges]
  );


  const savedWordIds = useMemo(
    () =>
      rangesToWordSet(
        savedWordRanges
      ),
    [savedWordRanges]
  );


  const manualSelectionDirty = useMemo(
    () => {
      const current = (
        wordSetToRanges(
          selectedWordIds
        )
      );

      const saved = (
        wordSetToRanges(
          savedWordIds
        )
      );

      return (
        JSON.stringify(current)
        !==
        JSON.stringify(saved)
      );
    },
    [
      selectedWordIds,
      savedWordIds
    ]
  );


  function changeWordSelection(
    wordId,
    selected
  ) {
    const next = new Set(
      selectedWordIds
    );

    const id = Number(
      wordId
    );

    if (selected) {
      next.add(id);
    } else {
      next.delete(id);
    }

    setWordRanges(
      wordSetToRanges(
        next
      )
    );
  }


  function beginWordDrag(
    event,
    wordId
  ) {
    event.preventDefault();

    if (
      selection?.status
      !== "draft"
    ) {
      return;
    }

    const id = Number(
      wordId
    );

    const mode = (
      selectedWordIds.has(id)
      ? "remove"
      : "add"
    );

    setDragMode(mode);

    changeWordSelection(
      id,
      mode === "add"
    );
  }


  function continueWordDrag(
    wordId
  ) {
    if (!dragMode) {
      return;
    }

    changeWordSelection(
      Number(wordId),
      dragMode === "add"
    );
  }


  function toggleSentence(
    sentenceWords
  ) {
    if (
      !sentenceWords.length
      ||
      selection?.status
      !== "draft"
    ) {
      return;
    }

    const next = new Set(
      selectedWordIds
    );

    const allSelected = (
      sentenceWords.every(
        word =>
          next.has(
            Number(word.id)
          )
      )
    );

    for (
      const word
      of sentenceWords
    ) {
      const id = Number(
        word.id
      );

      if (allSelected) {
        next.delete(id);
      } else {
        next.add(id);
      }
    }

    setWordRanges(
      wordSetToRanges(
        next
      )
    );
  }


  async function saveManualRanges(
    nextRanges
  ) {
    if (
      !selection
      || selection.status
         !== "draft"
    ) {
      return;
    }

    setBusy(true);
    setError("");

    try {
      setActivity(
        "Saving manual selection..."
      );

      const updated = await api(
        `${API}/selections/${selection.id}`,
        {
          method: "PUT",
          body: JSON.stringify({
            revision:
              selection.revision,

            selected_segment_ids:
              [...selectedIds]
                .map(Number)
                .sort(
                  (a, b) =>
                    a - b
                ),

            word_ranges:
              nextRanges
          })
        }
      );

      const savedRanges = (
        updated.word_ranges
        || []
      );

      setSelection(
        updated
      );

      setSelectedIds(
        updated
          .selected_segment_ids
        || []
      );

      setWordRanges(
        savedRanges
      );

      setSavedWordRanges(
        savedRanges
      );

      setWordStart(null);
      setWordEnd(null);
      setActivity("");

    } catch (err) {
      setError(err.message);
      setActivity("");

    } finally {
      setBusy(false);
    }
  }


  async function saveCurrentWordRange() {
    if (
      wordStart === null
      || wordEnd === null
    ) {
      return;
    }

    const start = Math.min(
      Number(wordStart),
      Number(wordEnd)
    );

    const end = Math.max(
      Number(wordStart),
      Number(wordEnd)
    );

    const nextRange = {
      start_word_id: start,
      end_word_id: end
    };

    const exists = (
      wordRanges.some(
        range =>
          sameRange(
            range,
            nextRange
          )
      )
    );

    const nextRanges = (
      exists
      ? wordRanges
      : [
          ...wordRanges,
          nextRange
        ]
    );

    await saveManualRanges(
      nextRanges
    );
  }


  async function removeWordRange(
    index
  ) {
    const nextRanges = (
      wordRanges.filter(
        (_, itemIndex) =>
          itemIndex !== index
      )
    );

    await saveManualRanges(
      nextRanges
    );
  }


  async function saveDraft() {
    if (!selection) {
      throw new Error(
        "Selection draft is missing."
      );
    }

    if (
      selection.status
      !== "draft"
    ) {
      return selection;
    }

    setActivity(
      "Saving review changes..."
    );

    const updated = await api(
      `${API}/selections/${selection.id}`,
      {
        method: "PUT",
        body: JSON.stringify({
          revision:
            selection.revision,

          selected_segment_ids:
            [...selectedIds]
              .map(Number)
              .sort(
                (a, b) => a - b
              ),

          word_ranges:
            wordRanges
        })
      }
    );

    setSelection(updated);
    setSelectedIds(
      updated.selected_segment_ids
      || []
    );

    const savedRanges = (
      updated.word_ranges
      || []
    );

    setWordRanges(
      savedRanges
    );

    setSavedWordRanges(
      savedRanges
    );

    setActivity("");

    return updated;
  }


  async function saveOnly() {
    setBusy(true);
    setError("");

    try {
      await saveDraft();

    } catch (err) {
      setError(err.message);
      setActivity("");

    } finally {
      setBusy(false);
    }
  }


  async function approveSelection() {
    setBusy(true);
    setError("");

    try {
      const saved = await saveDraft();

      if (
        !saved.resolved_clips?.length
      ) {
        throw new Error(
          "Select at least one transcript segment or word range."
        );
      }

      setActivity(
        "Approving final edit..."
      );

      const approved = await api(
        `${API}/selections/${saved.id}/approve`,
        {
          method: "POST",
          body: JSON.stringify({
            revision:
              saved.revision
          })
        }
      );

      setSelection(
        approved
      );

      setStep(3);
      setActivity("");

    } catch (err) {
      setError(err.message);
      setActivity("");

    } finally {
      setBusy(false);
    }
  }


  function removeRenderAsset(
    asset,
    setter
  ) {
    if (asset?.previewUrl) {
      URL.revokeObjectURL(
        asset.previewUrl
      );
    }

    setter(null);
    setRender(null);
    setResult(null);
  }


  async function uploadRenderAsset(
    kind,
    file,
    setter,
    existingAsset
  ) {
    if (!file) {
      return;
    }

    const extension = (
      file.name
        .toLowerCase()
        .split(".")
        .pop()
    );

    if (extension !== "mp4") {
      setError(
        "Intro and outro videos must be MP4 files."
      );

      return;
    }

    const maxBytes = (
      100 * 1024 * 1024
    );

    if (
      file.size <= 0
      || file.size > maxBytes
    ) {
      setError(
        "Intro and outro videos must be 100 MB or smaller."
      );

      return;
    }

    setBusy(true);
    setError("");
    setRender(null);
    setResult(null);

    try {
      setActivity(
        `Preparing ${kind} upload...`
      );

      const upload = await api(
        `${API}/render-assets/uploads`,
        {
          method: "POST",
          body: JSON.stringify({
            kind,
            filename:
              file.name,

            content_type:
              "video/mp4",

            size_bytes:
              file.size
          })
        }
      );

      const form = new FormData();

      for (
        const [key, value]
        of Object.entries(
          upload.upload_fields
          || {}
        )
      ) {
        form.append(
          key,
          value
        );
      }

      form.append(
        "file",
        file,
        file.name
      );

      setActivity(
        `Uploading ${kind} video...`
      );

      const response = await fetch(
        upload.upload_url,
        {
          method:
            upload.upload_method
            || "POST",

          body:
            form
        }
      );

      if (!response.ok) {
        throw new Error(
          `S3 ${kind} upload failed: `
          + response.status
        );
      }

      setActivity(
        `Validating ${kind} video...`
      );

      const completed = await api(
        (
          `${API}/render-assets/`
          + upload.asset_id
          + "/complete"
        ),
        {
          method: "POST"
        }
      );

      if (
        completed.status
        !== "ready"
      ) {
        throw new Error(
          `${kind} video is not ready.`
        );
      }

      if (
        existingAsset
        ?.previewUrl
      ) {
        URL.revokeObjectURL(
          existingAsset.previewUrl
        );
      }

      setter({
        id:
          completed.id,

        kind:
          completed.kind,

        filename:
          completed.filename,

        sizeBytes:
          completed.size_bytes,

        previewUrl:
          URL.createObjectURL(
            file
          )
      });

      setActivity("");

    } catch (err) {
      setError(
        err.message
      );

      setActivity("");

    } finally {
      setBusy(false);
    }
  }


  async function generateVideo() {
    if (!selection) {
      return;
    }

    setBusy(true);
    setError("");
    setResult(null);

    try {
      setActivity(
        "Queueing video render..."
      );

      let renderData = await api(
        `${API}/renders`,
        {
          method: "POST",
          body: JSON.stringify({
            selection_id:
              selection.id,

            intro_asset_id:
              introAsset?.id
              || null,

            outro_asset_id:
              outroAsset?.id
              || null
          })
        }
      );

      setRender(
        renderData
      );

      if (
        renderData.status
        !== "completed"
      ) {
        setActivity(
          "Rendering selected clips..."
        );

        renderData = (
          await waitForJob(
            `${API}/renders/${renderData.id}`,
            {
              interval: 2500,
              timeout:
                60 * 60 * 1000
            }
          )
        );

        setRender(
          renderData
        );
      }

      setActivity(
        "Loading generated result..."
      );

      const output = await api(
        `${API}/renders/${renderData.id}/result`
      );

      setResult(output);
      setActivity("");

    } catch (err) {
      setError(err.message);
      setActivity("");

    } finally {
      setBusy(false);
    }
  }


  const tentativeStart = (
    wordStart !== null
    && wordEnd !== null
      ? Math.min(
          wordStart,
          wordEnd
        )
      : wordStart
  );

  const tentativeEnd = (
    wordStart !== null
    && wordEnd !== null
      ? Math.max(
          wordStart,
          wordEnd
        )
      : wordStart
  );


  const tentativeDetails = (
    wordStart !== null
    && wordEnd !== null
      ? rangeDetails(
          wordStart,
          wordEnd
        )
      : null
  );


  return (
    <div className="app">
      <header className="topbar">
        <div>
          <div className="brand">
            DT-FlashCut
          </div>

          <div className="subtitle">
            Transcript-driven video editing
          </div>
        </div>

        <div className="api-status">
          DT-FlashCut API
        </div>
      </header>

      <main className="shell">
        <nav className="steps">
          {(
            workflow === "notes"
              ? [
                  "Source",
                  "Workflow",
                  "Notes",
                  "Export"
                ]
              : [
                  "Source",
                  "Workflow",
                  "Review",
                  "Generate"
                ]
          ).map(
            (label, index) => (
              <button
                key={label}
                className={
                  "step "
                  + (
                    step === index
                    ? "active"
                    : ""
                  )
                  + (
                    step > index
                    ? " complete"
                    : ""
                  )
                }
                disabled={
                  index > step
                }
                onClick={() => {
                  if (
                    index <= step
                  ) {
                    setStep(index);
                  }
                }}
              >
                <span>
                  {index + 1}
                </span>

                {label}
              </button>
            )
          )}
        </nav>

        {error && (
          <div className="alert error">
            {error}
          </div>
        )}

        {activity && (
          <div className="alert activity">
            <span className="spinner" />
            {activity}
          </div>
        )}

        {step === 0 && (
          <section className="panel">
            <div className="panel-heading">
              <div>
                <p className="eyebrow">
                  STEP 1
                </p>

                <h1>
                  Select source video
                </h1>

                <p>
                  Videos are read from the
                  configured S3 source.
                  The source video is not
                  displayed in the browser.
                </p>
              </div>

              <button
                className="secondary"
                onClick={loadVideos}
                disabled={busy}
              >
                Refresh
              </button>
            </div>

            <label className="field">
              <span>
                Video
              </span>

              <select
                value={videoId}
                onChange={
                  event =>
                    setVideoId(
                      event.target.value
                    )
                }
              >
                {videos.map(
                  video => (
                    <option
                      key={video.id}
                      value={video.id}
                    >
                      {video.name}
                    </option>
                  )
                )}
              </select>
            </label>

            {currentVideo && (
              <div className="source-card">
                <strong>
                  {currentVideo.name}
                </strong>

                <span>
                  Video ID:
                  {" "}
                  {currentVideo.id}
                </span>
              </div>
            )}

            <div className="actions end">
              <button
                className="primary"
                disabled={
                  !videoId
                  || busy
                }
                onClick={() =>
                  setStep(1)
                }
              >
                Continue
              </button>
            </div>
          </section>
        )}

        {step === 1 && (
          <section className="panel">
            <p className="eyebrow">
              STEP 2
            </p>

            <h1>
              Choose workflow
            </h1>

            <p>
              Both workflows use the
              server-authoritative transcript
              and timestamps.
            </p>

            <div className="workflow-grid">
              <button
                className={
                  "workflow-card "
                  + (
                    workflow
                    === "automatic"
                    ? "selected"
                    : ""
                  )
                }
                onClick={() =>
                  setWorkflow(
                    "automatic"
                  )
                }
              >
                <span className="workflow-title">
                  Automatic summary
                </span>

                <span>
                  AI selects the
                  highest-value learning
                  moments from the full
                  transcript.
                </span>

                <span className="workflow-note">
                  You review and edit every
                  selection before rendering.
                </span>
              </button>

              <button
                className={
                  "workflow-card "
                  + (
                    workflow
                    === "manual"
                    ? "selected"
                    : ""
                  )
                }
                onClick={() =>
                  setWorkflow(
                    "manual"
                  )
                }
              >
                <span className="workflow-title">
                  Manual selection
                </span>

                <span>
                  Start with the full
                  transcript and choose
                  transcript segments or
                  exact words yourself.
                </span>

                <span className="workflow-note">
                  No AI summary selection
                  is applied.
                </span>
              </button>
            </div>

            <button
              type="button"
              className={
                "workflow-card "
                + (
                  workflow === "notes"
                    ? "selected"
                    : ""
                )
              }
              onClick={() =>
                setWorkflow(
                  "notes"
                )
              }
            >
              <span className="workflow-title">
                Automatic Notes
              </span>

              <span>
                Convert the video directly
                into editable educational
                notes from the transcript.
              </span>

              <span className="workflow-note">
                Standard, Crisp or High-yield.
                Optional Mind Map, Flowchart
                and PDF export.
              </span>
            </button>

            {workflow === "notes" && (
              <div className="duration">
                <strong>
                  Notes style
                </strong>

                <div className="note-style-grid">
                  {[
                    {
                      id: "standard",
                      title: "Standard",
                      description:
                        "Structured teaching notes"
                    },
                    {
                      id: "crisp",
                      title: "Crisp",
                      description:
                        "Short revision notes"
                    },
                    {
                      id: "high_yield",
                      title: "High-yield",
                      description:
                        "Priority learning points"
                    }
                  ].map(
                    item => (
                      <button
                        type="button"
                        key={item.id}
                        className={
                          "note-style-option "
                          + (
                            noteStyle
                            === item.id
                              ? "selected"
                              : ""
                          )
                        }
                        onClick={() =>
                          setNoteStyle(
                            item.id
                          )
                        }
                      >
                        <strong>
                          {item.title}
                        </strong>

                        <span>
                          {
                            item.description
                          }
                        </span>
                      </button>
                    )
                  )}
                </div>
              </div>
            )}

            {workflow === "automatic" && (
              <div className="duration">
                <label className="field">
                  <span>
                    Maximum summary duration
                  </span>

                  <select
                    value={
                      targetMinutes
                    }
                    onChange={
                      event =>
                        setTargetMinutes(
                          Number(
                            event.target
                              .value
                          )
                        )
                    }
                  >
                    <option value="5">
                      5 minutes
                    </option>

                    <option value="10">
                      10 minutes
                    </option>

                    <option value="15">
                      15 minutes
                    </option>

                    <option value="20">
                      20 minutes
                    </option>

                    <option value="30">
                      30 minutes
                    </option>
                  </select>
                </label>

                <p className="help">
                  This is a maximum budget,
                  not a quota. Automatic
                  summary may return a
                  shorter edit when the
                  transcript does not contain
                  enough high-value material.
                </p>
              </div>
            )}

            <div className="actions">
              <button
                className="secondary"
                disabled={busy}
                onClick={() =>
                  setStep(0)
                }
              >
                Back
              </button>

              <button
                className="primary"
                disabled={busy}
                onClick={() => {
                  if (
                    workflow === "notes"
                  ) {
                    setStep(2);
                    return;
                  }

                  prepareWorkflow();
                }}
              >
                {
                  workflow === "automatic"
                    ? "Create automatic summary"
                    : workflow === "notes"
                    ? "Continue to Notes"
                    : "Prepare manual selection"
                }
              </button>
            </div>
          </section>
        )}

        {(
          workflow === "notes"
          && (
            step === 2
            || step === 3
          )
        ) && (
          <NotesWorkflow
            videoId={videoId}
            videoName={
              currentVideo?.name
              || "Video"
            }
            noteStyle={noteStyle}
            step={step}
            setStep={setStep}
          />
        )}

        {step === 2 && workflow !== "notes" && transcript && (
          <section className="panel wide">
            <div className="review-header">
              <div>
                <p className="eyebrow">
                  STEP 3
                </p>

                <h1>
                  Review edit
                </h1>

                <p>
                  Remove AI-selected
                  timestamps, add transcript
                  segments, or add exact word
                  ranges before approval.
                </p>
              </div>

              <div className="metrics">
                <div>
                  <strong>
                    {selectedIds.length}
                  </strong>
                  <span>
                    segments
                  </span>
                </div>

                <div>
                  <strong>
                    {
                      wordRanges.length
                    }
                  </strong>
                  <span>
                    word ranges
                  </span>
                </div>

                <div>
                  <strong>
                    {
                      selection
                      ? formatSeconds(
                          selection
                            .total_seconds
                        )
                      : "0:00"
                    }
                  </strong>
                  <span>
                    saved duration
                  </span>
                </div>
              </div>
            </div>

            {summary && (
              <div className="summary-box">
                <div>
                  <span className="badge">
                    Automatic summary
                  </span>

                  <h2>
                    {
                      summary.notes?.title
                      || "Learning summary"
                    }
                  </h2>

                  <div className="topics">
                    {
                      summary.coverage_topics
                        ?.map(
                          topic => (
                            <span
                              key={topic}
                            >
                              {topic}
                            </span>
                          )
                        )
                    }
                  </div>
                </div>

                <div>
                  <strong>
                    {
                      formatSeconds(
                        summary
                          .selected_seconds
                      )
                    }
                  </strong>

                  <p>
                    AI selected duration
                  </p>
                </div>
              </div>
            )}

            {summary?.notes?.bullets
              ?.length > 0 && (
              <div className="learning-notes">
                <h3>
                  Learning notes
                </h3>

                <ul>
                  {
                    summary.notes.bullets
                      .map(
                        (
                          bullet,
                          index
                        ) => (
                          <li
                            key={index}
                          >
                            {bullet}
                          </li>
                        )
                      )
                  }
                </ul>
              </div>
            )}

            {workflow === "automatic" && (
            <section className="selection-section segment-selection-section">
              <div className="section-heading">
                <div>
                  <span className="section-number">
                    A
                  </span>

                  <div>
                    <h2>
                      Automatic summary selection
                    </h2>

                    <p>
                      Review the transcript
                      segments selected by the
                      automatic summary.
                    </p>
                  </div>
                </div>
              </div>

              <div className="review-toolbar">
              <p className="section-help">
                Click the checkbox to include or
                remove the complete sentence or
                segment.
              </p>

              <label className="check-label">
                <input
                  type="checkbox"
                  checked={
                    showSelectedOnly
                  }
                  onChange={
                    event =>
                      setShowSelectedOnly(
                        event.target
                          .checked
                      )
                  }
                />

                Show selected only
              </label>
            </div>

            <div className="segments">
              {displayedSegments.map(
                segment => {
                  const selected = (
                    selectedIds.includes(
                      Number(
                        segment.id
                      )
                    )
                  );

                  const ai = (
                    summaryBySegment.get(
                      Number(
                        segment.id
                      )
                    )
                  );

                  return (
                    <label
                      key={segment.id}
                      className={
                        "segment "
                        + (
                          selected
                          ? "selected"
                          : ""
                        )
                      }
                      onClick={() => {
                        if (
                          selection?.status
                          === "draft"
                        ) {
                          toggleSegment(
                            segment.id
                          );
                        }
                      }}
                    >
                      <input
                        type="checkbox"
                        checked={selected}
                        disabled={
                          selection?.status
                          !== "draft"
                        }
                        onClick={
                          event =>
                            event.stopPropagation()
                        }
                        onChange={() =>
                          toggleSegment(
                            segment.id
                          )
                        }
                      />

                      <div>
                        <div className="segment-meta">
                          <span className="timestamp-chip">
                            {
                              formatTimestamp(
                                segment.start
                              )
                            }
                            {" – "}
                            {
                              formatTimestamp(
                                segment.end
                              )
                            }
                          </span>

                          {ai && (
                            <>
                              <span>
                                Importance:
                                {" "}
                                {
                                  ai.importance
                                }
                              </span>

                              {ai.critical && (
                                <span className="critical">
                                  Critical
                                </span>
                              )}

                              <span>
                                {ai.topic}
                              </span>
                            </>
                          )}
                        </div>

                        <p>
                          {segment.text}
                        </p>

                        {ai?.learning_point && (
                          <small>
                            {
                              ai.learning_point
                            }
                          </small>
                        )}
                      </div>
                    </label>
                  );
                }
              )}
            </div>
            </section>

            )}

            <section className="timestamp-selection-panel">
              <div className="timestamp-selection-header">
                <div>
                  <h2>
                    Timestamp selection
                  </h2>

                  <p>
                    Select complete transcript
                    ranges using their video
                    timestamps.
                  </p>
                </div>

                <div className="timestamp-selection-count">
                  <strong>
                    {selectedIds.length}
                  </strong>

                  <span>
                    selected ranges
                  </span>
                </div>
              </div>

              <div className="timestamp-selection-help">
                Click any row to include or remove
                that complete timestamp range.
              </div>

              <div className="timestamp-list">
                {(transcript?.segments || []).map(
                  segment => {
                    const segmentId = Number(
                      segment.id
                    );

                    const selected = (
                      selectedIds.includes(
                        segmentId
                      )
                    );

                    return (
                      <label
                        key={
                          `timestamp-${segmentId}`
                        }
                        className={
                          "timestamp-row "
                          + (
                            selected
                              ? "selected"
                              : ""
                          )
                        }
                      >
                        <input
                          type="checkbox"
                          checked={selected}
                          disabled={
                            selection?.status
                            !== "draft"
                          }
                          onChange={() =>
                            toggleSegment(
                              segmentId
                            )
                          }
                        />

                        <div className="timestamp-row-content">
                          <div className="timestamp-value">
                            {
                              formatTimestamp(
                                segment.start
                              )
                            }
                            {" – "}
                            {
                              formatTimestamp(
                                segment.end
                              )
                            }
                          </div>

                          <div className="timestamp-text">
                            {segment.text}
                          </div>
                        </div>

                        {selected && (
                          <span className="timestamp-selected-badge">
                            Selected
                          </span>
                        )}
                      </label>
                    );
                  }
                )}
              </div>

              <div className="timestamp-selection-footer">
                <span>
                  Selected timestamp ranges are
                  saved together with your word
                  selections in the same draft.
                </span>

                <button
                  className="primary"
                  disabled={
                    busy
                    || selection?.status
                       !== "draft"
                  }
                  onClick={
                    saveOnly
                  }
                >
                  Save timestamp draft
                </button>
              </div>
            </section>

            <section className="manual-selection">
              <div className="manual-selection-header">
                <div>
                  <h2>
                    Word selection
                  </h2>

                  <p>
                    Click individual words or
                    drag across multiple words.
                    Selected words are highlighted
                    and saved as part of the draft.
                  </p>
                </div>

                <div
                  className={
                    "draft-state "
                    + (
                      manualSelectionDirty
                      ? "unsaved"
                      : "saved"
                    )
                  }
                >
                  {
                    manualSelectionDirty
                    ? "Unsaved changes"
                    : "Draft saved"
                  }
                </div>
              </div>

              <div className="selection-toolbar">
                <div>
                  <strong>
                    {
                      selectedWordIds.size
                    }
                  </strong>

                  <span>
                    selected words
                  </span>
                </div>

                <div>
                  <strong>
                    {
                      wordRanges.length
                    }
                  </strong>

                  <span>
                    selected ranges
                  </span>
                </div>

                <button
                  className="secondary"
                  disabled={
                    busy
                    || !selectedWordIds.size
                  }
                  onClick={() => {
                    setWordRanges([]);
                  }}
                >
                  Clear selection
                </button>

                <button
                  className="primary"
                  disabled={
                    busy
                    || !manualSelectionDirty
                  }
                  onClick={
                    saveOnly
                  }
                >
                  Save draft
                </button>
              </div>

              <div className="selection-legend">
                <span>
                  <i className="legend-selected" />
                  Selected
                </span>

                <span>
                  <i className="legend-persisted" />
                  Saved in draft
                </span>

                <span className="selection-help">
                  Click and drag to select multiple words
                </span>
              </div>

              <div className="paragraph-selector">
                {wordGroups.map(
                  ({
                    segment,
                    words:
                      sentenceWords
                  }) => {
                    const sentenceSelected = (
                      sentenceWords.length > 0
                      &&
                      sentenceWords.every(
                        word =>
                          selectedWordIds.has(
                            Number(
                              word.id
                            )
                          )
                      )
                    );

                    return (
                      <span
                        className="selectable-sentence"
                        key={
                          `paragraph-${segment.id}`
                        }
                      >
                        {sentenceWords.map(
                          word => {
                            const id = Number(
                              word.id
                            );

                            const selected = (
                              selectedWordIds
                                .has(id)
                            );

                            const saved = (
                              savedWordIds
                                .has(id)
                              && selected
                            );

                            return (
                              <button
                                type="button"
                                key={id}
                                className={
                                  "selectable-word "
                                  + (
                                    selected
                                    ? "selected "
                                    : ""
                                  )
                                  + (
                                    saved
                                    ? "persisted"
                                    : ""
                                  )
                                }
                                title={
                                  formatTimestamp(
                                    word.start
                                  )
                                  + " – "
                                  + formatTimestamp(
                                    word.end
                                  )
                                }
                                disabled={
                                  selection?.status
                                  !== "draft"
                                }
                                onPointerDown={
                                  event =>
                                    beginWordDrag(
                                      event,
                                      id
                                    )
                                }
                                onPointerEnter={() =>
                                  continueWordDrag(
                                    id
                                  )
                                }
                              >
                                {word.text}
                              </button>
                            );
                          }
                        )}

                        {" "}
                      </span>
                    );
                  }
                )}
              </div>

              <div className="selection-summary">
                <div className="selection-summary-heading">
                  <div>
                    <h3>
                      Selected ranges
                    </h3>

                    <p>
                      Every range shows the exact
                      video timestamps that will
                      be included.
                    </p>
                  </div>

                  <span className="range-count">
                    {wordRanges.length}
                  </span>
                </div>

                {wordRanges.length === 0 ? (
                  <div className="empty-selection">
                    Select words or sentences
                    from the transcript above.
                  </div>
                ) : (
                  <div className="selected-range-list">
                    {wordRanges.map(
                      (range, index) => {
                        const details = (
                          rangeDetails(
                            range.start_word_id,
                            range.end_word_id
                          )
                        );

                        const persisted = (
                          savedWordRanges.some(
                            savedRange =>
                              sameRange(
                                savedRange,
                                range
                              )
                          )
                        );

                        if (!details) {
                          return null;
                        }

                        return (
                          <div
                            className="selected-range-card"
                            key={
                              `${range.start_word_id}-${range.end_word_id}-${index}`
                            }
                          >
                            <div className="selected-range-top">
                              <div className="selected-range-times">
                                <strong>
                                  {
                                    formatTimestamp(
                                      details.startTime
                                    )
                                  }
                                  {" – "}
                                  {
                                    formatTimestamp(
                                      details.endTime
                                    )
                                  }
                                </strong>

                                <span>
                                  {
                                    details.duration
                                      .toFixed(2)
                                  }
                                  {" sec"}
                                </span>

                                {persisted && (
                                  <span className="saved-tag">
                                    Saved draft
                                  </span>
                                )}
                              </div>

                              <button
                                type="button"
                                className="remove-selection"
                                disabled={busy}
                                onClick={() => {
                                  setWordRanges(
                                    current =>
                                      current.filter(
                                        (
                                          _,
                                          itemIndex
                                        ) =>
                                          itemIndex
                                          !== index
                                      )
                                  );
                                }}
                              >
                                Remove
                              </button>
                            </div>

                            <div className="selected-range-text">
                              {
                                details.words.map(
                                  word => (
                                    <span
                                      key={
                                        `range-${index}-${word.id}`
                                      }
                                    >
                                      {word.text}
                                    </span>
                                  )
                                )
                              }
                            </div>
                          </div>
                        );
                      }
                    )}
                  </div>
                )}
              </div>
            </section>

            <div className="actions sticky">
              <button
                className="secondary"
                disabled={busy}
                onClick={() =>
                  setStep(1)
                }
              >
                Back
              </button>

              <div className="action-group">
                <button
                  className="secondary"
                  disabled={
                    busy
                    || selection?.status
                       !== "draft"
                  }
                  onClick={
                    saveOnly
                  }
                >
                  Save draft
                </button>

                <button
                  className="primary"
                  disabled={
                    busy
                    || selection?.status
                       !== "draft"
                  }
                  onClick={
                    approveSelection
                  }
                >
                  Approve selection
                </button>
              </div>
            </div>
          </section>
        )}

        {step === 3 && workflow !== "notes" && selection && (
          <section className="panel">
            <p className="eyebrow">
              STEP 4
            </p>

            <h1>
              Generate video
            </h1>

            <p>
              The approved transcript
              selection is immutable.
              DT-FlashCut will render only
              the server-resolved clips.
            </p>

            <div className="generate-card">
              <div>
                <span>
                  Approved clips
                </span>

                <strong>
                  {
                    selection
                      .resolved_clips
                      ?.length || 0
                  }
                </strong>
              </div>

              <div>
                <span>
                  Edited duration
                </span>

                <strong>
                  {
                    formatSeconds(
                      selection
                        .total_seconds
                    )
                  }
                </strong>
              </div>

              <div>
                <span>
                  Status
                </span>

                <strong>
                  {
                    render?.status
                    || "Ready"
                  }
                </strong>
              </div>
            </div>

            {!result && (
              <div className="render-assets-section">
                <div className="render-assets-heading">
                  <h2>
                    Intro and outro
                  </h2>

                  <p>
                    Optional MP4 videos.
                    Each file can be up to
                    100 MB and 60 seconds.
                  </p>
                </div>

                <div className="render-assets-grid">
                  <div className="render-asset-card">
                    <div>
                      <span className="badge">
                        Optional
                      </span>

                      <h3>
                        Intro video
                      </h3>

                      <p>
                        Plays before the
                        edited content.
                      </p>
                    </div>

                    {!introAsset && (
                      <label className="asset-upload">
                        <span>
                          Choose intro MP4
                        </span>

                        <input
                          type="file"
                          accept="video/mp4,.mp4"
                          disabled={busy}
                          onChange={event => {
                            const file = (
                              event
                                .target
                                .files?.[0]
                            );

                            event.target.value =
                              "";

                            void uploadRenderAsset(
                              "intro",
                              file,
                              setIntroAsset,
                              introAsset
                            );
                          }}
                        />
                      </label>
                    )}

                    {introAsset && (
                      <div className="asset-ready">
                        <video
                          className="asset-preview"
                          src={
                            introAsset
                              .previewUrl
                          }
                          controls
                          preload="metadata"
                        />

                        <strong>
                          {
                            introAsset
                              .filename
                          }
                        </strong>

                        <span>
                          {(
                            introAsset
                              .sizeBytes
                            / 1024
                            / 1024
                          ).toFixed(2)}
                          {" MB"}
                        </span>

                        <button
                          type="button"
                          className="secondary"
                          disabled={busy}
                          onClick={() =>
                            removeRenderAsset(
                              introAsset,
                              setIntroAsset
                            )
                          }
                        >
                          Remove intro
                        </button>
                      </div>
                    )}
                  </div>

                  <div className="render-asset-card">
                    <div>
                      <span className="badge">
                        Optional
                      </span>

                      <h3>
                        Outro video
                      </h3>

                      <p>
                        Plays after the
                        edited content.
                      </p>
                    </div>

                    {!outroAsset && (
                      <label className="asset-upload">
                        <span>
                          Choose outro MP4
                        </span>

                        <input
                          type="file"
                          accept="video/mp4,.mp4"
                          disabled={busy}
                          onChange={event => {
                            const file = (
                              event
                                .target
                                .files?.[0]
                            );

                            event.target.value =
                              "";

                            void uploadRenderAsset(
                              "outro",
                              file,
                              setOutroAsset,
                              outroAsset
                            );
                          }}
                        />
                      </label>
                    )}

                    {outroAsset && (
                      <div className="asset-ready">
                        <video
                          className="asset-preview"
                          src={
                            outroAsset
                              .previewUrl
                          }
                          controls
                          preload="metadata"
                        />

                        <strong>
                          {
                            outroAsset
                              .filename
                          }
                        </strong>

                        <span>
                          {(
                            outroAsset
                              .sizeBytes
                            / 1024
                            / 1024
                          ).toFixed(2)}
                          {" MB"}
                        </span>

                        <button
                          type="button"
                          className="secondary"
                          disabled={busy}
                          onClick={() =>
                            removeRenderAsset(
                              outroAsset,
                              setOutroAsset
                            )
                          }
                        >
                          Remove outro
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}

            {!result && (
              <button
                className="primary large"
                disabled={busy}
                onClick={
                  generateVideo
                }
              >
                Generate edited video
              </button>
            )}

            {result && (
              <div className="result-card">
                <div>
                  <span className="badge success">
                    Completed
                  </span>

                  <h2>
                    {result.filename}
                  </h2>

                  <p>
                    {
                      result.size_bytes
                      ? `${(
                          result.size_bytes
                          / 1024
                          / 1024
                        ).toFixed(2)} MB`
                      : ""
                    }
                  </p>
                </div>

                <a
                  className="primary link-button"
                  href={result.url}
                  target="_blank"
                  rel="noreferrer"
                >
                  Open generated video
                </a>
              </div>
            )}

            <div className="actions">
              <button
                className="secondary"
                disabled={busy}
                onClick={() =>
                  setStep(2)
                }
              >
                Review
              </button>

              <button
                className="secondary"
                disabled={busy}
                onClick={() => {
                  setStep(0);
                  setTranscript(null);
                  setWords([]);
                  setSummary(null);
                  setSelection(null);
                  setRender(null);
                  setResult(null);

                  if (
                    introAsset
                      ?.previewUrl
                  ) {
                    URL.revokeObjectURL(
                      introAsset
                        .previewUrl
                    );
                  }

                  if (
                    outroAsset
                      ?.previewUrl
                  ) {
                    URL.revokeObjectURL(
                      outroAsset
                        .previewUrl
                    );
                  }

                  setIntroAsset(null);
                  setOutroAsset(null);
                  setSelectedIds([]);
                  setWordRanges([]);
                  setSavedWordRanges([]);
                }}
              >
                Start new edit
              </button>
            </div>
          </section>
        )}
      </main>
    </div>
  );
}


createRoot(
  document.getElementById("root")
).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
