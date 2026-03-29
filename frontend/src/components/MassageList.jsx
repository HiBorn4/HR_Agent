import React, { useEffect, useRef, useState } from 'react';
import { useAuthStore } from '../features/auth/store';
import ReactMarkdown from 'react-markdown';
import { doc, onSnapshot } from 'firebase/firestore'; 
import { db } from '../api/firebase'; 
import { submitFeedbackAPI } from '../api/api'; 

// --- 0. REAL-TIME PROCESSING INDICATOR (Glass Box) ---
const ProcessingIndicator = ({ sessionId }) => {
  const [status, setStatus] = useState({ current_step: "Connecting to Agent...", steps: [] });
  const [expanded, setExpanded] = useState(true); 
  const [elapsedTime, setElapsedTime] = useState(0);

  useEffect(() => {
    const timer = setInterval(() => setElapsedTime((prev) => prev + 1), 1000);
    return () => clearInterval(timer);
  }, []);

  const formatTime = (seconds) => {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return m > 0 ? `${m}m ${s}s` : `${s}s`;
  };

  useEffect(() => {
    if (!sessionId) return;
    const statusRef = doc(db, "chat_sessions", sessionId, "run_status", "latest");
    const unsubscribe = onSnapshot(statusRef, (docSnapshot) => {
      if (docSnapshot.exists()) {
        setStatus(docSnapshot.data());
      }
    }, (error) => {
      console.error("Failed to subscribe to Glass Box updates:", error);
    });

    return () => unsubscribe();
  }, [sessionId]);

  return (
    <div className="w-full max-w-md my-2">
      <div 
        className="flex items-center gap-3 cursor-pointer p-3 bg-gray-900/60 rounded-xl border border-gray-700/50 hover:bg-gray-800 transition-colors shadow-sm" 
        onClick={() => setExpanded(!expanded)}
      >
        <div className="relative flex items-center justify-center w-5 h-5">
           <div className="absolute w-full h-full border-2 border-red-500/30 rounded-full"></div>
           <div className="absolute w-full h-full border-t-2 border-red-500 rounded-full animate-spin"></div>
        </div>

        <div className="flex-1 flex justify-between items-center">
          <p className="text-sm font-semibold text-transparent bg-clip-text bg-gradient-to-r from-red-400 to-orange-400 animate-pulse">
            {status.current_step}
          </p>
          <span className="text-xs font-mono text-gray-400 bg-gray-800 px-2 py-1 rounded-md">
            ⏱️ {formatTime(elapsedTime)}
          </span>
        </div>
        
        <div className={`text-gray-500 transition-transform duration-300 ${expanded ? 'rotate-180' : ''}`}>
          ▼
        </div>
      </div>

      <div className={`overflow-hidden transition-all duration-300 ease-in-out ${expanded ? 'max-h-60 mt-3 opacity-100' : 'max-h-0 opacity-0'}`}>
        <div className="bg-[#0a0a0a] rounded-lg border border-gray-800 p-3 text-xs font-mono space-y-2 overflow-y-auto max-h-56 shadow-inner">
          <div className="flex justify-between border-b border-gray-800 pb-1 mb-2">
             <span className="text-[10px] text-gray-500 uppercase tracking-widest">Agent Audit Trail</span>
             <span className="text-[10px] text-gray-500">Time Elapsed: {formatTime(elapsedTime)}</span>
          </div>
          
          {status.steps && status.steps.length > 0 ? status.steps.map((step, idx) => (
            <div key={idx} className="flex gap-3 border-l-2 border-gray-700 pl-3 py-1">
               <span className="text-gray-500 whitespace-nowrap">
                 {step.timestamp?.seconds 
                    ? new Date(step.timestamp.seconds * 1000).toLocaleTimeString([], {hour12: false, hour:'2-digit', minute:'2-digit', second:'2-digit'}) 
                    : '--:--:--'}
               </span>
               <span className={`${step.status === 'ERROR' ? 'text-red-400 font-bold' : 'text-green-400 font-semibold'}`}>
                 [{step.status || 'INFO'}]
               </span>
               <span className="text-gray-300 break-words">{step.step}</span>
            </div>
          )) : (
            <div className="text-gray-600 italic">Initializing agent logic...</div>
          )}
          <div className="text-gray-600 italic animate-pulse mt-2">...awaiting next instruction...</div>
        </div>
      </div>
    </div>
  );
};

// --- 1. SMART TABLE COMPONENT ---
const SmartTable = ({ data }) => {
  if (!data || data.length === 0) return null;

  const isStructured = data.headers && data.rows;
  const rawRows = isStructured ? data.rows : data;
  
  if (!Array.isArray(rawRows) || rawRows.length === 0) return null;

  let headers = [];
  if (isStructured && data.headers) {
    headers = data.headers.map(h => ({ key: h.field, label: h.headerName }));
  } else {
    const allKeys = new Set();
    rawRows.forEach(row => {
      if (typeof row === 'object' && row !== null) {
        Object.keys(row).forEach(k => allKeys.add(k));
      }
    });
    headers = Array.from(allKeys).map(k => ({ key: k, label: k }));
  }

  const renderCell = (value) => {
    if (value === null || value === undefined) return <span className="text-gray-600">-</span>;
    if (typeof value === 'object') {
      return JSON.stringify(value);
    }
    return String(value);
  };

  return (
    <div className="mt-4 overflow-x-auto rounded-lg border border-gray-700 bg-[#1a1c1e]">
      {data.title && <div className="px-4 py-2 bg-gray-800 font-semibold border-b border-gray-700 text-red-400">{data.title}</div>}
      {data.description && <div className="px-4 py-2 text-xs text-gray-400 border-b border-gray-700">{data.description}</div>}
      
      <table className="min-w-full text-sm text-left text-gray-300">
        <thead className="text-xs text-white uppercase bg-gray-700">
          <tr>
            {headers.map((h) => (
              <th key={h.key} className="px-6 py-3 font-medium border-b border-gray-600 whitespace-nowrap">
                {h.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-700">
          {rawRows.map((row, rIdx) => (
            <tr key={rIdx} className="hover:bg-gray-700 transition-colors">
              {headers.map((h) => (
                <td key={h.key} className="px-6 py-4 whitespace-nowrap">
                  {renderCell(row[h.key])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

// --- 2. MESSAGE ITEM COMPONENT ---
const MessageItem = ({ message, prevUserMessage, user, onAskQuestion }) => {
  const [showLogic, setShowLogic] = useState(false);
  
  // Feedback System States
  const [feedbackState, setFeedbackState] = useState(null); // 'good', 'bad', 'submitted'
  const [isFormOpen, setIsFormOpen] = useState(false);
  const [feedbackText, setFeedbackText] = useState("");
  const [copied, setCopied] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleCopy = () => {
    const textToCopy = message.text || message.data?.summaryText || "";
    navigator.clipboard.writeText(textToCopy);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleRedo = () => {
    if (prevUserMessage && onAskQuestion) {
      onAskQuestion(prevUserMessage);
    }
  };

  const submitFeedback = async (type, text = "") => {
    try {
      setIsSubmitting(true);
      const sessionId = message.sessionId || localStorage.getItem("session_id");
      const userId = localStorage.getItem("user_id");
      
      await submitFeedbackAPI({
        session_id: sessionId,
        message_id: String(message.id),
        feedback_type: type,
        feedback_text: text,
        user_id: userId
      });
      
      setFeedbackState(type === 'good' ? 'good' : 'submitted');
      setIsFormOpen(false);
    } catch (error) {
      console.error("Failed to submit feedback", error);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleFeedbackClick = (type) => {
    if (type === 'good') {
      submitFeedback('good');
    } else if (type === 'bad') {
      setFeedbackState('bad');
      setIsFormOpen(true);
    }
  };

  const renderMessageText = (text) => {
    if (!text) return null;
    
    const graphKeyword = "GRAPH:";
    if (text.includes(graphKeyword)) {
      const parts = text.split(graphKeyword);
      const textContent = parts[0];
      const graphContent = parts[1]?.trim();
      
      let imageSrc = graphContent;
      if (graphContent && !graphContent.startsWith('http') && !graphContent.startsWith('data:')) {
        imageSrc = `data:image/png;base64,${graphContent}`;
      }

      return (
        <div className="space-y-4">
          <ReactMarkdown>{textContent}</ReactMarkdown>
          {graphContent && (
             <div className="mt-4 p-2 bg-gray-900 rounded-lg border border-gray-700 shadow-sm">
                <img 
                  src={imageSrc} 
                  alt="Graph visualization" 
                  className="w-full h-auto rounded object-contain"
                  onError={(e) => {
                     console.error("Failed to load graph image");
                     e.target.style.display = 'none'; 
                  }}
                />
             </div>
          )}
        </div>
      );
    }
    return <ReactMarkdown>{text}</ReactMarkdown>;
  };

  const renderStructuredResponse = (data) => {
    return (
      <div className="space-y-4 w-full">
        {data?.summaryText && (
          <div className="text-base leading-relaxed text-gray-100">
            <ReactMarkdown 
              components={{
                p: ({node, ...props}) => <p className="mb-2" {...props} />,
                ul: ({node, ...props}) => <ul className="list-disc ml-4 mb-2" {...props} />,
                ol: ({node, ...props}) => <ol className="list-decimal ml-4 mb-2" {...props} />,
                li: ({node, ...props}) => <li className="mb-1" {...props} />,
                a: ({node, ...props}) => <a className="text-blue-400 hover:underline" {...props} />,
              }}
            >
              {data.summaryText}
            </ReactMarkdown>
          </div>
        )}

        {data?.tables?.length > 0 && data.tables.map((tableData, idx) => (
          <SmartTable key={idx} data={tableData} />
        ))}

        {data?.plotly_html && (
          <div className="mt-6 w-full rounded-xl overflow-hidden border border-gray-700/50 bg-[#121212] shadow-2xl relative" style={{ height: '520px', minWidth: '100%' }}>
            <iframe
              title="Interactive Chart"
              style={{ width: '100%', height: '100%', border: 'none' }}
              sandbox="allow-scripts allow-same-origin allow-downloads"
              srcDoc={`
                <!DOCTYPE html>
                <html>
                  <head>
                    <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
                    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
                    <style>
                      body { 
                        margin: 0; 
                        padding: 0; 
                        background-color: transparent; 
                        overflow: hidden; 
                        display: flex;
                        justify-content: center;
                        align-items: center;
                      }
                    </style>
                  </head>
                  <body>
                    ${data.plotly_html}
                  </body>
                </html>
              `}
            />
          </div>
        )}

        {data?.image_base64 && !data?.plotly_html && (
          <div className="mt-4 rounded-lg overflow-hidden border border-gray-700">
             <img 
               src={`data:image/png;base64,${data.image_base64}`} 
               alt="AI Generated Visualization" 
               className="w-full h-auto object-contain bg-black/50"
             />
             <div className="px-3 py-2 bg-gray-800 text-xs text-gray-400 flex justify-between items-center">
               <span>Static AI Generated Visual</span>
               <a href={`data:image/png;base64,${data.image_base64}`} download="mahindra-chart.png" className="text-blue-400 hover:text-blue-300 transition-colors">
                 <i className="fas fa-download mr-1"></i> Download Image
               </a>
             </div>
          </div>
        )}

        {data?.summary && Object.entries(data.summary).map(([key, value]) => {
          if (Array.isArray(value) && value.length > 0) {
            return (
              <div key={key} className="mt-4 bg-gray-900/50 p-4 rounded-lg border border-gray-800">
                <h4 className="font-semibold text-red-400 mb-2 capitalize border-b border-gray-700 pb-2">
                  {key.replace(/([A-Z])/g, " $1")}
                </h4>
                <ul className="space-y-2 text-sm">
                  {value.map((item, idx) => (
                    <li key={idx} className="flex flex-wrap gap-x-4 gap-y-1">
                      {typeof item === 'object' ? Object.entries(item).map(([k, v]) => (
                        <span key={k} className="text-gray-300">
                          <strong className="text-gray-500 mr-1">{k}:</strong>{v}
                        </span>
                      )) : <span className="text-gray-300">{item}</span>}
                    </li>
                  ))}
                </ul>
              </div>
            );
          }
          return null;
        })}
      </div>
    );
  };

  return (
    <div className={`flex w-full ${message.type === 'user' ? 'justify-end' : 'justify-start'}`}>
      <div className={`flex ${message.type === 'user' ? 'flex-row-reverse' : 'flex-row'} max-w-[95%] md:max-w-[85%] lg:max-w-[80%] gap-3 w-full`}>
        
        <div className="flex-shrink-0 w-8 h-8 md:w-10 md:h-10 rounded-full overflow-hidden shadow-sm border border-gray-700 bg-black mt-1">
          {message.type === 'assistant' ? (
            <div className="w-full h-full bg-gray-800 flex items-center justify-center">
              <span className="text-lg">🤖</span>
            </div>
          ) : (
            <img
              src={user?.picture || 'https://i.pravatar.cc/150?img=3'}
              alt="User"
              className="w-full h-full object-cover"
            />
          )}
        </div>

        <div className={`flex flex-col p-4 md:p-5 rounded-2xl shadow-lg transition-all w-full ${
          message.type === 'user'
            ? 'bg-gradient-to-br from-[#e31837] to-[#b3122c] text-white rounded-tr-sm self-end max-w-fit'
            : 'bg-[#1a1c1e] border border-gray-800 text-gray-100 rounded-tl-sm w-full'
        }`}>
          <div className="prose prose-invert max-w-none w-full text-sm md:text-base overflow-hidden">
            {message.isLoading ? (
               <ProcessingIndicator sessionId={message.sessionId} />
            ) : message.data ? (
              renderStructuredResponse(message.data)
            ) : (
              renderMessageText(message.text)
            )}
          </div>

          {/* AI Message Action Bar (Gemini Style) */}
          {message.type === 'assistant' && !message.isLoading && (
            <div className="mt-4 pt-3 border-t border-gray-700/50">
              <div className="flex items-center gap-2">
                
                {/* Good Response */}
                <button 
                  onClick={() => handleFeedbackClick('good')}
                  className={`p-2 rounded-full hover:bg-gray-800 transition-colors ${feedbackState === 'good' ? 'text-green-500 bg-green-500/10' : 'text-gray-400 hover:text-gray-200'}`}
                  title="Good response"
                >
                  <i className={feedbackState === 'good' ? "fa-solid fa-thumbs-up" : "fa-regular fa-thumbs-up"}></i>
                </button>

                {/* Bad Response */}
                <button 
                  onClick={() => handleFeedbackClick('bad')}
                  className={`p-2 rounded-full hover:bg-gray-800 transition-colors ${feedbackState === 'bad' || feedbackState === 'submitted' ? 'text-red-500 bg-red-500/10' : 'text-gray-400 hover:text-gray-200'}`}
                  title="Bad response"
                >
                  <i className={feedbackState === 'bad' || feedbackState === 'submitted' ? "fa-solid fa-thumbs-down" : "fa-regular fa-thumbs-down"}></i>
                </button>

                <div className="h-4 w-px bg-gray-700 mx-1"></div>

                {/* Copy */}
                <button 
                  onClick={handleCopy}
                  className="p-2 rounded-full hover:bg-gray-800 transition-colors text-gray-400 hover:text-gray-200"
                  title="Copy response"
                >
                  {copied ? <i className="fa-solid fa-check text-green-500"></i> : <i className="fa-regular fa-copy"></i>}
                </button>

                {/* Redo */}
                {prevUserMessage && (
                  <button 
                    onClick={handleRedo}
                    className="p-2 rounded-full hover:bg-gray-800 transition-colors text-gray-400 hover:text-gray-200"
                    title="Regenerate draft"
                  >
                    <i className="fa-solid fa-rotate-right"></i>
                  </button>
                )}

                {/* Debug Info Toggle */}
                {message.data?.debugInfo && (
                  <button 
                    onClick={() => setShowLogic(!showLogic)}
                    className="ml-auto text-xs font-mono text-gray-500 hover:text-gray-300 transition-colors"
                  >
                    {showLogic ? '</Hide Logic>' : '<View Logic>'}
                  </button>
                )}
              </div>

              {/* Bad Feedback Form Dropdown */}
              {isFormOpen && (
                <div className="mt-4 p-4 bg-[#121212] border border-red-900/50 rounded-xl animate-in fade-in slide-in-from-top-2">
                  <h4 className="text-sm font-semibold text-gray-200 mb-2">Provide additional feedback</h4>
                  <textarea
                    value={feedbackText}
                    onChange={(e) => setFeedbackText(e.target.value)}
                    placeholder="What was wrong with this response? (This will be sent to the data team)"
                    className="w-full bg-black border border-gray-700 rounded-lg p-3 text-sm text-gray-300 focus:outline-none focus:border-red-500 min-h-[80px]"
                  />
                  <div className="flex justify-end gap-3 mt-3">
                    <button 
                      onClick={() => setIsFormOpen(false)}
                      className="px-4 py-2 text-xs font-medium text-gray-400 hover:text-white transition-colors"
                    >
                      Cancel
                    </button>
                    <button 
                      onClick={() => submitFeedback('bad', feedbackText)}
                      disabled={isSubmitting || !feedbackText.trim()}
                      className="px-4 py-2 text-xs font-medium bg-red-600 hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-lg transition-colors"
                    >
                      {isSubmitting ? 'Submitting...' : 'Submit Feedback'}
                    </button>
                  </div>
                </div>
              )}

              {/* Submitted Confirmation */}
              {feedbackState === 'submitted' && (
                <div className="mt-2 text-xs text-red-400 italic">
                  Thank you. Your feedback has been logged and sent to the admin.
                </div>
              )}

              {/* Debug Logic Block */}
              {showLogic && message.data?.debugInfo && (
                <div className="mt-3 p-3 bg-black/40 rounded-md border border-gray-700 overflow-x-auto">
                  <pre className="text-xs text-green-400 font-mono whitespace-pre-wrap">
                    {message.data.debugInfo}
                  </pre>
                </div>
              )}
            </div>
          )}

          {/* Suggestion Chips */}
          {message.type === 'assistant' && !message.isLoading && message.data?.suggestions && message.data.suggestions.length > 0 && (
             <div className="mt-4 flex flex-wrap gap-2 animate-in fade-in slide-in-from-top-2 duration-500">
               {message.data.suggestions.map((suggestion, idx) => (
                 <button
                   key={idx}
                   onClick={() => onAskQuestion(suggestion)}
                   className="px-3 py-1.5 bg-blue-500/10 hover:bg-blue-500/20 border border-blue-500/30 text-blue-300 text-xs rounded-full transition-colors flex items-center gap-1"
                 >
                   <span>✨</span> {suggestion}
                 </button>
               ))}
             </div>
          )}
        </div>
      </div>
    </div>
  );
};

// --- 3. MAIN LIST COMPONENT ---
const MassageList = ({ messages, onAskQuestion }) => {
  const lastMessageRef = useRef(null);
  const user = useAuthStore((state) => state.user);

  useEffect(() => {
    if (lastMessageRef.current) {
      lastMessageRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages]);

  return (
    <div className="flex flex-col space-y-6 pb-4 w-full">
      {messages.map((message, index) => {
        // Pass previous user query to "Redo" functionality
        const prevMessage = index > 0 ? messages[index - 1] : null;
        const prevUserMessage = prevMessage && prevMessage.type === 'user' ? prevMessage.text : null;

        return (
          <MessageItem 
            key={message.id || index}
            message={message}
            prevUserMessage={prevUserMessage}
            user={user}
            onAskQuestion={onAskQuestion}
          />
        );
      })}
      <div ref={lastMessageRef} />
    </div>
  );
};

export default MassageList;