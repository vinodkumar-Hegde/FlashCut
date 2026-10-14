import React, {
  useMemo,
  useState
} from "react";

import "./notes.css";


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
    throw new Error(
      data?.error?.message
      || `Request failed: ${response.status}`
    );
  }

  return data;
}


async function waitForNote(
  noteId
) {
  for (
    let attempt = 0;
    attempt < 300;
    attempt += 1
  ) {
    const note = await api(
      `${API}/notes/${noteId}`
    );

    if (
      note.status === "completed"
    ) {
      return note;
    }

    if (
      note.status === "failed"
    ) {
      throw new Error(
        note.failure_reason
        || "Notes generation failed."
      );
    }

    await new Promise(
      resolve =>
        setTimeout(
          resolve,
          2500
        )
    );
  }

  throw new Error(
    "Timed out waiting for notes."
  );
}


function buildChildren(
  visual
) {
  const children = new Map();

  for (
    const node
    of visual.nodes || []
  ) {
    children.set(
      node.id,
      []
    );
  }

  for (
    const edge
    of visual.edges || []
  ) {
    if (
      children.has(
        edge.source
      )
    ) {
      children
        .get(
          edge.source
        )
        .push({
          nodeId:
            edge.target,

          label:
            edge.label || ""
        });
    }
  }

  return children;
}


function buildFlowLevels(
  visual
) {
  const nodes = (
    visual.nodes || []
  );

  const edges = (
    visual.edges || []
  );

  const ids = new Set(
    nodes.map(
      node => node.id
    )
  );

  const incoming = new Map(
    nodes.map(
      node => [
        node.id,
        0
      ]
    )
  );

  const outgoing = new Map(
    nodes.map(
      node => [
        node.id,
        []
      ]
    )
  );

  for (const edge of edges) {
    if (
      !ids.has(edge.source)
      || !ids.has(edge.target)
    ) {
      continue;
    }

    incoming.set(
      edge.target,
      (
        incoming.get(
          edge.target
        )
        || 0
      ) + 1
    );

    outgoing
      .get(
        edge.source
      )
      .push(edge);
  }

  const roots = nodes
    .filter(
      node =>
        incoming.get(
          node.id
        ) === 0
    )
    .map(
      node => node.id
    );

  const level = new Map();

  const queue = roots.map(
    id => ({
      id,
      level: 0
    })
  );

  while (queue.length) {
    const current = (
      queue.shift()
    );

    const existing = (
      level.get(
        current.id
      )
    );

    if (
      existing !== undefined
      && existing
         >= current.level
    ) {
      continue;
    }

    level.set(
      current.id,
      current.level
    );

    for (
      const edge
      of outgoing.get(
        current.id
      ) || []
    ) {
      queue.push({
        id:
          edge.target,

        level:
          current.level + 1
      });
    }
  }

  const grouped = new Map();

  for (const node of nodes) {
    const itemLevel = (
      level.get(
        node.id
      )
      ?? 0
    );

    if (
      !grouped.has(
        itemLevel
      )
    ) {
      grouped.set(
        itemLevel,
        []
      );
    }

    grouped
      .get(
        itemLevel
      )
      .push(node);
  }

  return {
    levels:
      [...grouped.entries()]
        .sort(
          (
            [left],
            [right]
          ) =>
            left - right
        )
        .map(
          ([, items]) =>
            items
        ),

    outgoing
  };
}


function MindMapDiagram({
  visual
}) {
  const nodes = (
    visual.nodes || []
  );

  const byId = new Map(
    nodes.map(
      node => [
        node.id,
        node
      ]
    )
  );

  const children = (
    buildChildren(
      visual
    )
  );

  const root = (
    byId.get(
      visual.root_id
    )
    || nodes[0]
  );

  if (!root) {
    return null;
  }

  const branches = (
    children.get(
      root.id
    )
    || []
  );

  return (
    <div className="mindmap-modern">
      <div className="mindmap-modern-root">
        {root.label}
      </div>

      <div className="mindmap-root-line" />

      <div className="mindmap-modern-branches">
        {branches.map(
          branchEdge => {
            const branch = (
              byId.get(
                branchEdge.nodeId
              )
            );

            if (!branch) {
              return null;
            }

            const leaves = (
              children.get(
                branch.id
              )
              || []
            );

            return (
              <div
                className="mindmap-modern-branch"
                key={branch.id}
              >
                <div className="mindmap-branch-line" />

                <div
                  className="mindmap-branch-title"
                  title={
                    branch.detail
                    || branch.label
                  }
                >
                  {
                    branch.detail
                    || branch.label
                  }
                </div>

                <div className="mindmap-leaves">
                  {leaves.map(
                    leafEdge => {
                      const leaf = (
                        byId.get(
                          leafEdge.nodeId
                        )
                      );

                      if (!leaf) {
                        return null;
                      }

                      return (
                        <div
                          key={leaf.id}
                          className="mindmap-leaf"
                          title={
                            leaf.detail
                            || leaf.label
                          }
                        >
                          {
                            leaf.detail
                            || leaf.label
                          }
                        </div>
                      );
                    }
                  )}
                </div>
              </div>
            );
          }
        )}
      </div>
    </div>
  );
}


function FlowchartDiagram({
  visual
}) {
  if (
    visual.available === false
  ) {
    return (
      <div className="flow-unavailable">
        <strong>
          No meaningful flowchart available
        </strong>

        <p>
          {visual.reason}
        </p>
      </div>
    );
  }

  const {
    levels,
    outgoing
  } = buildFlowLevels(
    visual
  );

  return (
    <div className="flowchart-modern">
      {levels.map(
        (
          nodes,
          levelIndex
        ) => (
          <React.Fragment
            key={
              `level-${levelIndex}`
            }
          >
            <div className="flowchart-level">
              {nodes.map(
                node => {
                  const links = (
                    outgoing.get(
                      node.id
                    )
                    || []
                  );

                  return (
                    <div
                      className="flowchart-node-wrap"
                      key={node.id}
                    >
                      <div
                        className={
                          "flowchart-modern-node "
                          + (
                            node.type
                            || "process"
                          )
                        }
                        title={
                          node.detail
                          || node.label
                        }
                      >
                        {node.type
                          === "decision"
                          && (
                            <span className="flow-node-type">
                              Decision
                            </span>
                          )}

                        <span>
                          {node.label}
                        </span>
                      </div>

                      {links.some(
                        edge =>
                          edge.label
                      ) && (
                        <div className="flow-edge-labels">
                          {links
                            .filter(
                              edge =>
                                edge.label
                            )
                            .map(
                              edge => (
                                <span
                                  key={
                                    `${edge.source}-${edge.target}`
                                  }
                                >
                                  {edge.label}
                                </span>
                              )
                            )}
                        </div>
                      )}
                    </div>
                  );
                }
              )}
            </div>

            {levelIndex
              < levels.length - 1
              && (
                <div className="flowchart-connector">
                  <span>
                    ↓
                  </span>
                </div>
              )}
          </React.Fragment>
        )
      )}
    </div>
  );
}


function Diagram({
  visual
}) {
  if (!visual) {
    return null;
  }

  return (
    <div className="notes-diagram modern">
      <div className="notes-diagram-title">
        <span>
          {
            visual.kind
            === "mindmap"
              ? "Mind Map"
              : "Flowchart"
          }
        </span>

        <strong>
          {visual.title}
        </strong>
      </div>

      {visual.kind === "mindmap" ? (
        <MindMapDiagram
          visual={visual}
        />
      ) : (
        <FlowchartDiagram
          visual={visual}
        />
      )}
    </div>
  );
}


export default function NotesWorkflow({
  videoId,
  videoName,
  noteStyle,
  step,
  setStep
}) {
  const [
    note,
    setNote
  ] = useState(null);

  const [
    content,
    setContent
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


  const dirty = useMemo(
    () => (
      note
      && content
      && JSON.stringify(
        content
      )
      !== JSON.stringify(
        note.content
      )
    ),
    [
      note,
      content
    ]
  );


  function updateContent(
    callback
  ) {
    setContent(
      current => {
        const copy = (
          structuredClone(
            current
          )
        );

        callback(copy);

        return copy;
      }
    );
  }


  async function generateNotes() {
    setBusy(true);
    setError("");

    try {
      setActivity(
        "Preparing transcript and generating notes..."
      );

      let result = await api(
        `${API}/notes`,
        {
          method: "POST",
          body: JSON.stringify({
            video_id: videoId,
            style: noteStyle
          })
        }
      );

      if (
        result.status
        !== "completed"
      ) {
        result = await waitForNote(
          result.id
        );
      }

      setNote(result);

      setContent(
        structuredClone(
          result.content
        )
      );

      setActivity("");

    } catch (err) {
      setError(err.message);
      setActivity("");

    } finally {
      setBusy(false);
    }
  }


  async function saveNotes() {
    if (
      !note
      || !content
    ) {
      return note;
    }

    if (!dirty) {
      return note;
    }

    setActivity(
      "Saving notes..."
    );

    const updated = await api(
      `${API}/notes/${note.id}`,
      {
        method: "PUT",
        body: JSON.stringify({
          revision:
            note.revision,

          content
        })
      }
    );

    setNote(updated);

    setContent(
      structuredClone(
        updated.content
      )
    );

    setActivity("");

    return updated;
  }


  async function generateVisual(
    kind
  ) {
    setBusy(true);
    setError("");

    try {
      const saved = (
        await saveNotes()
      );

      if (!saved) {
        return;
      }

      setActivity(
        kind === "mindmap"
          ? "Generating mind map..."
          : "Generating flowchart..."
      );

      const updated = await api(
        `${API}/notes/${saved.id}/visuals`,
        {
          method: "POST",
          body: JSON.stringify({
            revision:
              saved.revision,

            kind
          })
        }
      );

      setNote(updated);

      setContent(
        structuredClone(
          updated.content
        )
      );

      setActivity("");

    } catch (err) {
      setError(err.message);
      setActivity("");

    } finally {
      setBusy(false);
    }
  }


  async function continueToExport() {
    setBusy(true);
    setError("");

    try {
      await saveNotes();
      setStep(3);

    } catch (err) {
      setError(err.message);

    } finally {
      setBusy(false);
      setActivity("");
    }
  }


  if (step === 3) {
    return (
      <section className="panel notes-export">
        <p className="eyebrow">
          STEP 4
        </p>

        <h1>
          Export Notes
        </h1>

        <p>
          Export the latest saved notes,
          including generated visual aids,
          as a branded PDF.
        </p>

        <div className="notes-export-card">
          <img
            src="/doctutorials-logo.png"
            alt="Tutorials"
          />

          <div>
            <strong>
              {
                content?.title
                || "Automatic Notes"
              }
            </strong>

            <span>
              {videoName}
            </span>

            <span>
              {
                noteStyle
                  .replace(
                    "_",
                    " "
                  )
              }
              {" notes"}
            </span>
          </div>
        </div>

        <div className="actions">
          <button
            className="secondary"
            onClick={() =>
              setStep(2)
            }
          >
            Back to Notes
          </button>

          <a
            className="primary link-button"
            href={
              `${API}/notes/${note.id}/pdf`
            }
            target="_blank"
            rel="noreferrer"
          >
            Export PDF
          </a>
        </div>
      </section>
    );
  }


  if (!note) {
    return (
      <section className="panel">
        <p className="eyebrow">
          STEP 3
        </p>

        <h1>
          Automatic Notes
        </h1>

        <p>
          Generate editable educational
          notes directly from the selected
          video's transcript.
        </p>

        <div className="notes-source-summary">
          <div>
            <span>
              Video
            </span>

            <strong>
              {videoName}
            </strong>
          </div>

          <div>
            <span>
              Notes style
            </span>

            <strong>
              {
                noteStyle
                  .replace(
                    "_",
                    " "
                  )
              }
            </strong>
          </div>
        </div>

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

        <div className="actions">
          <button
            className="secondary"
            disabled={busy}
            onClick={() =>
              setStep(1)
            }
          >
            Back
          </button>

          <button
            className="primary"
            disabled={busy}
            onClick={
              generateNotes
            }
          >
            Generate Notes
          </button>
        </div>
      </section>
    );
  }


  return (
    <section className="panel wide">
      <div className="notes-editor-header">
        <div>
          <p className="eyebrow">
            STEP 3
          </p>

          <h1>
            Automatic Notes
          </h1>

          <p>
            Edit any heading or learning point.
            Mind maps and flowcharts are generated
            only when you request them.
          </p>
        </div>

        <div
          className={
            "draft-state "
            + (
              dirty
                ? "unsaved"
                : "saved"
            )
          }
        >
          {
            dirty
              ? "Unsaved changes"
              : "Saved"
          }
        </div>
      </div>

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

      <div className="notes-document">
        <img
          className="notes-watermark"
          src="/doctutorials-logo.png"
          alt=""
        />

        <label className="note-field">
          <span>
            Title
          </span>

          <input
            value={
              content.title || ""
            }
            onChange={
              event =>
                updateContent(
                  draft => {
                    draft.title =
                      event.target.value;
                  }
                )
            }
          />
        </label>

        <label className="note-field">
          <span>
            Overview
          </span>

          <textarea
            rows="4"
            value={
              content.overview || ""
            }
            onChange={
              event =>
                updateContent(
                  draft => {
                    draft.overview =
                      event.target.value;
                  }
                )
            }
          />
        </label>

        <div className="note-sections">
          {(content.sections || []).map(
            (
              section,
              sectionIndex
            ) => (
              <div
                className="note-section-editor"
                key={
                  `section-${sectionIndex}`
                }
              >
                <div className="note-section-header">
                  <input
                    className="note-heading-input"
                    value={
                      section.heading
                    }
                    onChange={
                      event =>
                        updateContent(
                          draft => {
                            draft
                              .sections[
                                sectionIndex
                              ]
                              .heading =
                                event.target
                                  .value;
                          }
                        )
                    }
                  />

                  <button
                    type="button"
                    className="remove-note-item"
                    onClick={() =>
                      updateContent(
                        draft => {
                          draft.sections.splice(
                            sectionIndex,
                            1
                          );
                        }
                      )
                    }
                  >
                    Remove section
                  </button>
                </div>

                {(section.bullets || []).map(
                  (
                    bullet,
                    bulletIndex
                  ) => (
                    <div
                      className="note-bullet-editor"
                      key={
                        `bullet-${sectionIndex}-${bulletIndex}`
                      }
                    >
                      <span>
                        •
                      </span>

                      <textarea
                        rows="2"
                        value={
                          bullet.text
                        }
                        onChange={
                          event =>
                            updateContent(
                              draft => {
                                draft
                                  .sections[
                                    sectionIndex
                                  ]
                                  .bullets[
                                    bulletIndex
                                  ]
                                  .text =
                                    event
                                      .target
                                      .value;
                              }
                            )
                        }
                      />

                      <button
                        type="button"
                        className="remove-note-item"
                        onClick={() =>
                          updateContent(
                            draft => {
                              draft
                                .sections[
                                  sectionIndex
                                ]
                                .bullets
                                .splice(
                                  bulletIndex,
                                  1
                                );
                            }
                          )
                        }
                      >
                        Remove
                      </button>
                    </div>
                  )
                )}

                <button
                  type="button"
                  className="secondary compact"
                  onClick={() =>
                    updateContent(
                      draft => {
                        draft
                          .sections[
                            sectionIndex
                          ]
                          .bullets
                          .push({
                            text: "",
                            source_segment_ids: []
                          });
                      }
                    )
                  }
                >
                  Add learning point
                </button>
              </div>
            )
          )}
        </div>

        <button
          type="button"
          className="secondary"
          onClick={() =>
            updateContent(
              draft => {
                draft.sections.push({
                  heading:
                    "New section",

                  bullets: [{
                    text: "",
                    source_segment_ids: []
                  }]
                });
              }
            )
          }
        >
          Add section
        </button>

        <div className="notes-takeaways">
          <h2>
            Key Takeaways
          </h2>

          {(content.key_takeaways || []).map(
            (
              takeaway,
              index
            ) => (
              <div
                className="note-bullet-editor"
                key={
                  `takeaway-${index}`
                }
              >
                <span>
                  •
                </span>

                <textarea
                  rows="2"
                  value={
                    takeaway.text
                  }
                  onChange={
                    event =>
                      updateContent(
                        draft => {
                          draft
                            .key_takeaways[
                              index
                            ]
                            .text =
                              event.target
                                .value;
                        }
                      )
                  }
                />

                <button
                  type="button"
                  className="remove-note-item"
                  onClick={() =>
                    updateContent(
                      draft => {
                        draft
                          .key_takeaways
                          .splice(
                            index,
                            1
                          );
                      }
                    )
                  }
                >
                  Remove
                </button>
              </div>
            )
          )}

          <button
            type="button"
            className="secondary compact"
            onClick={() =>
              updateContent(
                draft => {
                  draft
                    .key_takeaways
                    .push({
                      text: "",
                      source_segment_ids: []
                    });
                }
              )
            }
          >
            Add takeaway
          </button>
        </div>
      </div>

      <section className="notes-visuals">
        <div className="notes-visuals-header">
          <div>
            <h2>
              Visual Learning Aids
            </h2>

            <p>
              Generate only the visual format
              you want.
            </p>
          </div>

          <div className="visual-buttons">
            <button
              className="secondary"
              disabled={busy}
              onClick={() =>
                generateVisual(
                  "mindmap"
                )
              }
            >
              Generate Mind Map
            </button>

            <button
              className="secondary"
              disabled={busy}
              onClick={() =>
                generateVisual(
                  "flowchart"
                )
              }
            >
              Generate Flowchart
            </button>
          </div>
        </div>

        {(note.visuals || []).length === 0 ? (
          <div className="visual-empty">
            No visual aid generated.
          </div>
        ) : (
          (note.visuals || []).map(
            visual => (
              <Diagram
                key={visual.kind}
                visual={visual}
              />
            )
          )
        )}
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
              || !dirty
            }
            onClick={
              saveNotes
            }
          >
            Save Notes
          </button>

          <button
            className="primary"
            disabled={busy}
            onClick={
              continueToExport
            }
          >
            Continue to Export
          </button>
        </div>
      </div>
    </section>
  );
}
