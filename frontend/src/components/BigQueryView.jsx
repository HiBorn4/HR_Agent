import MassageList from "./MassageList";
import logo from "../asset/mahindra-rise.png";
import Navbar from "../components/Navbar";
import { useState, useEffect } from "react";
import Cookies from "js-cookie";
import { useNavigate } from "react-router-dom";
import { useAuthStore } from "../features/auth/store";
import { chat, userInfo, fetchSuggestedQuestions } from "../api/api";

export default function BigQueryView() {
  const [prompt, setPrompt] = useState("");
  const [listening, setListening] = useState(false);
  const [loading, setLoading] = useState(false);

  const [suggestedQuestions, setSuggestedQuestions] = useState([]);
  const [questionsLoading, setQuestionsLoading] = useState(true);

  const messages = useAuthStore((state) => state.bigqueryMessages);
  const addMessage = useAuthStore((state) => state.addMessage);
  const user = useAuthStore((state) => state.user);
  const mode = useAuthStore((state) => state.mode);
  const navigate = useNavigate();
  const updateMessage = useAuthStore((state) => state.updateMessage);

  // 1. Fetch Dynamic Suggestions on Mount
  useEffect(() => {
    const loadQuestions = async () => {
      try {
        const result = await fetchSuggestedQuestions();
        if (result && result.data && Array.isArray(result.data)) {
          // 🛠️ FIX 3: Randomize the array and pick the top 6 questions
          const shuffledQuestions = [...result.data].sort(() => 0.5 - Math.random());
          setSuggestedQuestions(shuffledQuestions.slice(0, 6));
        }
      } catch (error) {
        console.error("Failed to load suggested questions", error);
      } finally {
        setQuestionsLoading(false);
      }
    };
    loadQuestions();
  }, []);

  // 2. Speech Recognition Logic
  useEffect(() => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) return;

    const recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.lang = "en-US";

    recognition.onresult = (event) => {
      let transcript = "";
      for (let i = event.resultIndex; i < event.results.length; i++) {
        transcript += event.results[i][0].transcript;
      }
      setPrompt(transcript);
      if (event.results[event.results.length - 1].isFinal) {
        setPrompt(transcript.trim());
      }
    };

    recognition.onend = () => setListening(false);
    if (listening) recognition.start();
    return () => recognition.stop();
  }, [listening]);

  // 3. Handle Send
  const handleSend = async (overridePrompt = null) => {
    const sessionId = localStorage.getItem("session_id");
    const userId = localStorage.getItem("user_id");
    const finalPrompt = overridePrompt || prompt;

    if (!sessionId || !userId || !finalPrompt.trim()) {
      if (!user) navigate("/login");
      return;
    }

    const userMessage = {
      id: Date.now(),
      text: finalPrompt,
      type: "user",
      timestamp: new Date().toISOString(),
    };
    addMessage("bigquery", userMessage);
    setPrompt("");

    const loaderId = Date.now() + 1;
    addMessage("bigquery", {
      id: loaderId,
      type: "assistant",
      isLoading: true,
      text: "Analyzing data...",
      timestamp: new Date().toISOString(),
      sessionId: sessionId // Pass sessionId to trigger ProcessingIndicator
    });

    try {
      const apiResponse = await chat({ 
        message: finalPrompt, 
        mode, 
        session_id: sessionId, 
        user_id: userId 
      });

      if (apiResponse.status === "ActionRequired") {
        updateMessage("bigquery", loaderId, {
          isLoading: false,
          text: apiResponse.summaryText,
          isActionRequired: true,
          data: apiResponse.data
        });
        return;
      }

      if (apiResponse.status === "Success" && apiResponse.data) {
        const structuredData = apiResponse.data;
        updateMessage("bigquery", loaderId, {
          isLoading: false,
          data: structuredData,
          text: structuredData.summaryText || "",
          relatedInsightQuestion: structuredData.relatedInsightQuestion || null,
        });
      }
    } catch (err) {
      console.error("Chat Error:", err);
      updateMessage("bigquery", loaderId, {
        isLoading: false,
        text: "An error occurred while processing your request.",
      });
    }
  };

  const handleAskRelatedQuestion = (question) => {
    setPrompt(question);
    handleSend(question); 
  };

  const msg = messages.length > 0;
  
  return (
    <div className="h-screen flex flex-col bg-black text-white">
      <div className="fixed top-0 left-0 right-0 z-50">
        <Navbar />
      </div>

      <main className="flex-1 overflow-y-auto pt-24 pb-40 px-6">
        <div className="max-w-6xl mx-auto">
          <div className="rounded-2xl border border-red-700/20 bg-gradient-to-br from-[#0f1112] to-[#111214] p-10 shadow-[0_10px_60px_rgba(0,0,0,0.6)]">
            {msg ? (
              <MassageList
                messages={messages}
                onAskQuestion={handleAskRelatedQuestion}
              />
            ) : (
              <div>
                <div className="flex flex-col items-center text-center gap-2 pb-6 border-b border-red-700/10">
                  <img src={logo} alt="Mahindra Rise" className="w-36 mb-8" />
                  <h1 className="text-4xl font-bold">Welcome, {user?.name}</h1>
                  <p className="max-w-2xl text-gray-400">
                    Select a suggested question below or type your own query to analyze HR data.
                  </p>
                </div>

                <div className="mt-8">
                  {questionsLoading ? (
                     <div className="flex justify-center items-center h-24 text-gray-500">
                        <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-red-600 mr-2"></div>
                        Loading suggestions...
                     </div>
                  ) : (
                    <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-6">
                      {suggestedQuestions.map((item, i) => (
                        <div
                          key={i}
                          onClick={() => handleSend(item.question || item)}
                          className="cursor-pointer bg-gray-900 hover:bg-gray-800 border border-gray-700 p-5 rounded-xl transition-all duration-200 hover:-translate-y-1 group relative overflow-hidden shadow-sm"
                        >
                          <div className="absolute top-0 left-0 w-1 h-full bg-red-600 transform scale-y-0 group-hover:scale-y-100 transition-transform duration-200"></div>
                          {item.category && (
                            <div className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
                              {item.category}
                            </div>
                          )}
                          <div className="text-gray-200 font-medium group-hover:text-white transition-colors">
                            {item.question || item}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      </main>

      <div className="fixed bottom-0 left-0 right-0 bg-gradient-to-t from-black via-black to-transparent py-6 z-40">
        <div className="max-w-6xl mx-auto px-6">
          <div className="flex items-center gap-4">
            <input
              value={prompt}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey && prompt.trim()) {
                  e.preventDefault();
                  handleSend();
                }
              }}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="Ask about attrition, hiring trends, or salary..."
              className="flex-1 bg-gray-900 border border-gray-800 placeholder-gray-500 text-gray-100 rounded-full px-6 py-4 focus:outline-none focus:ring-2 focus:ring-red-600"
            />
            <button
              onClick={() => setListening(true)}
              className="px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-xl shadow-lg transition flex items-center justify-center"
            >
              {listening ? <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin"></div> : "🎙️"}
            </button>
            <button
              onClick={() => handleSend()}
              className="px-6 py-3 bg-red-600 hover:bg-red-700 text-white rounded-xl shadow-lg transition"
            >
              Send
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}