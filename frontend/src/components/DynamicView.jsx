import MassageList from "./MassageList";
import logo from "../asset/mahindra-rise.png";
import Navbar from "../components/Navbar";
import { useState, useEffect } from "react";
// import Cookies from "js-cookie"; // Unused
import { useNavigate } from "react-router-dom";
import { useAuthStore } from "../features/auth/store";
import { chat, userInfo, fileUpload, api } from "../api/api";

export default function DynamicQueryView() {
  const [prompt, setPrompt] = useState("");
  const [listening, setListening] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);
  
  // [FIX] New state to track the successfully uploaded file
  const [uploadedFileName, setUploadedFileName] = useState(null);
  
  const [isUploading, setIsUploading] = useState(false);

  const user = useAuthStore((state) => state.user);
  const messages = useAuthStore((state) => state.dynamicMessages);
  const addMessage = useAuthStore((state) => state.addMessage);
  const updateMessage = useAuthStore((state) => state.updateMessage);
  
  const mode = useAuthStore((state) => state.mode);
  const setMode = useAuthStore((state) => state.setMode);

  const navigate = useNavigate();

  // 2. FORCE DYNAMIC MODE ON MOUNT AND PERSIST
  useEffect(() => {
    setMode("dynamic");
    localStorage.setItem("app_mode", "dynamic"); // [FIX] Persist mode
  }, [setMode]);

  const handleFileChange = (e) => {
    const file = e.target.files[0];
    setSelectedFile(file);
  };
  
  // [FIX] Function to reset file state for new upload
  const handleResetUpload = () => {
    setUploadedFileName(null);
    setSelectedFile(null);
  };

  // ... (Speech Recognition Logic remains the same) ...
  useEffect(() => {
    const SpeechRecognition =
      window.SpeechRecognition || window.webkitSpeechRecognition;

    if (!SpeechRecognition) {
      return;
    }

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

    recognition.onend = () => {
      setListening(false);
    };

    if (listening) {
      recognition.start();
    }

    return () => {
      recognition.stop();
    };
  }, [listening]);

  const handleSend = async () => {
    const sessionId = localStorage.getItem("session_id");
    const userId = localStorage.getItem("user_id");
    const finalPrompt = prompt;

    if (!sessionId || !userId) {
      navigate("/login");
      return;
    }
    
    if (!finalPrompt.trim() && !selectedFile) {
        return;
    }

    const userMessage = {
      id: Date.now(),
      text: finalPrompt || (selectedFile ? `Uploaded file: ${selectedFile.name}` : ""),
      type: "user",
      timestamp: new Date().toISOString(),
    };
    addMessage("dynamic", userMessage);
    setPrompt("");

    const loaderId = Date.now() + 1;
    addMessage("dynamic", {
      id: loaderId,
      type: "assistant",
      isLoading: true,
      text: selectedFile ? "Initiating upload..." : "Analyzing...",
      timestamp: new Date().toISOString(),
    });

    try {
      if (selectedFile) {
        setIsUploading(true);
        const formData = new FormData();
        formData.append("file", selectedFile);
        formData.append("user_id", userId);

        updateMessage("dynamic", loaderId, { 
            text: `Uploading ${selectedFile.name} to Cloud Storage...` 
        });

        const uploadResponse = await api.post("/api/upload", formData, {
            headers: { "Content-Type": "multipart/form-data" }
        });

        if (uploadResponse.data && uploadResponse.data.gcs_object_name) {
            updateMessage("dynamic", loaderId, { 
                text: "File uploaded. Processing data structure..." 
            });

            const processResponse = await fileUpload({ 
                gcs_object_name: uploadResponse.data.gcs_object_name 
            });
            
            console.log("File processed successfully:", processResponse);
            
            const rowCount = processResponse.shape ? processResponse.shape[0] : "data";
            updateMessage("dynamic", loaderId, { 
                text: `✅ File successfully uploaded! (${rowCount} rows loaded).\nNow running analysis on your data...` 
            });

            // [FIX] Update state to reflect active file
            setUploadedFileName(selectedFile.name);
            setSelectedFile(null); 
        } else {
            throw new Error("Upload failed: No GCS object name returned.");
        }
        setIsUploading(false);
      }

      const payload = {
        message: finalPrompt || "Analyze the uploaded file", 
        mode: "dynamic",
        session_id: sessionId,
        user_id: userId,
      };

      const apiResponse = await chat(payload);
      console.log("chat response:", apiResponse);

      if (apiResponse.status === "Success" && apiResponse.data) {
        const structuredData = apiResponse.data;

        updateMessage("dynamic", loaderId, {
          isLoading: false,
          type: "assistant",
          avatar: "https://i.pravatar.cc/40?img=1",
          timestamp: new Date().toISOString(),
          data: structuredData,
          text: structuredData.summaryText || "",
          relatedInsightQuestion: structuredData.relatedInsightQuestion || null,
        });
      } else {
        updateMessage("dynamic", loaderId, {
          isLoading: false,
          data: { summaryText: "No data available." },
          text: "No valid data returned.",
        });
      }

    } catch (error) {
      console.error("Request failed:", error);
      setIsUploading(false);
      updateMessage("dynamic", loaderId, {
        isLoading: false,
        data: { summaryText: error.response?.data?.error || error.message || "Error processing request." },
        text: "Error occurred.",
      });
    }
  };

  const handleAskRelatedQuestion = (question) => {
    setPrompt(question);
  };

  const sampleActions = [
    "Compare revenue by division",
    "Test the performance of a model",
    "Do an advanced time-series forecast",
    "Show top 5 employees by performance",
    "Show a correlation heatmap",
  ];
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
                    Select a mode to begin. Use BigQuery for database queries or
                    Dynamic Analysis to upload and analyze your own files.
                  </p>
                </div>

                <div className="mt-8 mb-4">
                  <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-6">
                    {sampleActions.map((a, i) => (
                      <button
                        key={i}
                        onClick={() => setPrompt(a)}
                        className="bg-transparent hover:bg-gray-800 border border-gray-700 text-gray-200 px-6 py-3 rounded-full shadow-sm text-sm transition"
                      >
                        {a}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </main>

      <div className="fixed bottom-0 left-0 right-0 bg-gradient-to-t from-black via-black to-transparent py-6 z-40">
        <div className="max-w-6xl mx-auto px-6">
          
          {/* [FIX] Dynamic Upload UI: Shows Active File or Upload Box */}
          {uploadedFileName && !selectedFile ? (
            <div className="border border-green-600/30 bg-green-900/10 rounded-xl p-4 flex items-center justify-between mb-4">
               <div className="flex items-center gap-3">
                 <div className="w-10 h-10 rounded-full bg-green-600/20 flex items-center justify-center text-green-500">
                    <i className="fas fa-file-csv"></i>
                 </div>
                 <div>
                    <p className="text-green-400 font-medium">Active File: {uploadedFileName}</p>
                    <p className="text-gray-500 text-xs">Ready for questions</p>
                 </div>
               </div>
               <button 
                  onClick={handleResetUpload}
                  className="px-4 py-2 bg-gray-800 hover:bg-gray-700 text-white text-sm rounded-lg border border-gray-700 transition"
               >
                  Upload New File
               </button>
            </div>
          ) : (
            <div className="border-2 border-dashed border-red-600 rounded-xl p-4 text-center bg-[#0f1112] mb-4 cursor-pointer hover:bg-[#151617] transition">
              <label className="block cursor-pointer">
                <p className="text-red-500 text-lg mb-4">
                   {selectedFile ? "📄 " + selectedFile.name : "📤 Choose a CSV or Excel file to upload"}
                </p>
                <input
                  type="file"
                  accept=".csv,.xlsx"
                  onChange={handleFileChange}
                  className="hidden"
                />
                <p className="text-gray-500 mt-2 text-sm">
                  {selectedFile ? "Ready to upload" : "No file selected."}
                </p>
              </label>
            </div>
          )}

          <div className="flex items-center gap-4">
            <input
              value={prompt}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey && (prompt.trim() || selectedFile)) {
                  e.preventDefault();
                  handleSend();
                }
              }}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="Compare revenue across divisions..."
              className="flex-1 bg-gray-900 border border-gray-800 placeholder-gray-500 text-gray-100 rounded-full px-6 py-4 focus:outline-none focus:ring-2 focus:ring-red-600"
            />
            <button
              onClick={() => setListening(true)}
              className="px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-xl shadow-lg transition flex items-center justify-center"
            >
              {listening ? (
                <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
              ) : (
                "🎙️"
              )}
            </button>
            {/* Removed "Test Model" dummy button for cleanliness */}
            <button
              onClick={handleSend}
              disabled={isUploading}
              className={`px-6 py-3 text-white rounded-xl shadow-lg transition ${
                  isUploading ? "bg-red-400 cursor-not-allowed" : "bg-red-600 hover:bg-red-700"
              }`}
            >
              {isUploading ? "Uploading..." : "Send"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}