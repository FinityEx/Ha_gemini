import React, { useState, useEffect, useRef } from 'react';
import { GoogleGenAI, Modality, LiveServerMessage } from '@google/genai';
import { Mic, MicOff, Lightbulb, Thermostat, Moon, Film, Power, Activity } from 'lucide-react';
import { motion } from 'motion/react';
import { AudioRecorder, AudioPlayer } from './lib/audioUtils';
import { haTools } from './lib/haTools';

const ai = new GoogleGenAI({ apiKey: process.env.GEMINI_API_KEY });

type DeviceState = {
  'light.living_room': boolean;
  'light.kitchen': boolean;
  'climate.living_room': number;
};

export default function App() {
  const [devices, setDevices] = useState<DeviceState>({
    'light.living_room': false,
    'light.kitchen': false,
    'climate.living_room': 72,
  });
  
  const [isListening, setIsListening] = useState(false);
  const [status, setStatus] = useState<string>('Ready');
  const [transcripts, setTranscripts] = useState<{role: string, text: string}[]>([]);
  
  const sessionRef = useRef<any>(null);
  const recorderRef = useRef<AudioRecorder | null>(null);
  const playerRef = useRef<AudioPlayer | null>(null);
  const transcriptEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [transcripts]);

  const toggleDevice = (entity_id: keyof DeviceState) => {
    if (typeof devices[entity_id] === 'boolean') {
      setDevices(prev => ({ ...prev, [entity_id]: !prev[entity_id] }));
    }
  };

  const startListening = async () => {
    try {
      setStatus('Connecting...');
      playerRef.current = new AudioPlayer();
      
      const sessionPromise = ai.live.connect({
        model: "gemini-2.5-flash-native-audio-preview-09-2025",
        config: {
          responseModalities: [Modality.AUDIO],
          systemInstruction: "You are a Home Assistant voice assistant. You can control devices, set temperatures, and activate scenes using the provided tools. Be concise, friendly, and helpful. Confirm actions after you perform them. The available devices are light.living_room, light.kitchen, climate.living_room. Available scenes are scene.goodnight, scene.movie_time.",
          tools: haTools,
          speechConfig: {
            voiceConfig: { prebuiltVoiceConfig: { voiceName: "Zephyr" } }
          },
          inputAudioTranscription: { model: "gemini-2.5-flash" },
          outputAudioTranscription: { model: "gemini-2.5-flash" },
        },
        callbacks: {
          onopen: () => {
            setStatus('Listening...');
            setIsListening(true);
            recorderRef.current = new AudioRecorder((base64Data) => {
              sessionPromise.then(session => {
                session.sendRealtimeInput({
                  media: { data: base64Data, mimeType: 'audio/pcm;rate=16000' }
                });
              });
            });
            recorderRef.current.start();
          },
          onmessage: async (message: LiveServerMessage) => {
            // Handle audio output
            const base64Audio = message.serverContent?.modelTurn?.parts[0]?.inlineData?.data;
            if (base64Audio && playerRef.current) {
              playerRef.current.playBase64Pcm(base64Audio);
            }
            
            // Handle interruption
            if (message.serverContent?.interrupted && playerRef.current) {
              playerRef.current.stop();
            }
            
            // Handle transcriptions
            const modelText = message.serverContent?.modelTurn?.parts[0]?.text;
            if (modelText) {
              setTranscripts(prev => [...prev, { role: 'assistant', text: modelText }]);
            }
            
            // Handle tool calls
            if (message.toolCall) {
              const functionCalls = message.toolCall.functionCalls;
              if (functionCalls) {
                const responses = [];
                for (const call of functionCalls) {
                  const name = call.name;
                  const args = call.args as any;
                  let result = { success: true, state: args };
                  
                  if (name === 'turn_on_device') {
                    setDevices(prev => ({ ...prev, [args.entity_id]: true }));
                  } else if (name === 'turn_off_device') {
                    setDevices(prev => ({ ...prev, [args.entity_id]: false }));
                  } else if (name === 'set_temperature') {
                    setDevices(prev => ({ ...prev, [args.entity_id]: args.temperature }));
                  } else if (name === 'activate_scene') {
                    if (args.scene_id === 'scene.goodnight') {
                      setDevices(prev => ({ ...prev, 'light.living_room': false, 'light.kitchen': false, 'climate.living_room': 68 }));
                    } else if (args.scene_id === 'scene.movie_time') {
                      setDevices(prev => ({ ...prev, 'light.living_room': false, 'light.kitchen': false, 'climate.living_room': 70 }));
                    }
                  }
                  
                  responses.push({
                    id: call.id,
                    name: call.name,
                    response: result
                  });
                }
                
                sessionPromise.then(session => {
                  session.sendToolResponse(responses);
                });
              }
            }
          },
          onclose: () => {
            setStatus('Disconnected');
            stopListening();
          },
          onerror: (err) => {
            console.error("Live API Error:", err);
            setStatus('Error occurred');
            stopListening();
          }
        }
      });
      
      sessionRef.current = sessionPromise;
      
    } catch (err) {
      console.error("Failed to start:", err);
      setStatus('Failed to connect');
    }
  };

  const stopListening = () => {
    if (recorderRef.current) {
      recorderRef.current.stop();
      recorderRef.current = null;
    }
    if (playerRef.current) {
      playerRef.current.stop();
      playerRef.current = null;
    }
    if (sessionRef.current) {
      sessionRef.current.then((session: any) => session.close());
      sessionRef.current = null;
    }
    setIsListening(false);
    setStatus('Ready');
  };

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 font-sans selection:bg-indigo-500/30">
      <div className="max-w-5xl mx-auto p-6 lg:p-12">
        
        <header className="mb-12 flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-semibold tracking-tight text-zinc-100 flex items-center gap-3">
              <Activity className="w-8 h-8 text-indigo-400" />
              Home Assistant
            </h1>
            <p className="text-zinc-400 mt-2 text-sm">Powered by Gemini Live API (STT, TTS, Conversation)</p>
          </div>
          
          <button
            onClick={isListening ? stopListening : startListening}
            className={`flex items-center gap-2 px-6 py-3 rounded-full font-medium transition-all duration-300 ${
              isListening 
                ? 'bg-red-500/10 text-red-400 border border-red-500/20 hover:bg-red-500/20' 
                : 'bg-indigo-500 text-white hover:bg-indigo-600 shadow-lg shadow-indigo-500/20'
            }`}
          >
            {isListening ? (
              <>
                <motion.div
                  animate={{ scale: [1, 1.2, 1] }}
                  transition={{ repeat: Infinity, duration: 1.5 }}
                >
                  <Mic className="w-5 h-5" />
                </motion.div>
                {status}
              </>
            ) : (
              <>
                <MicOff className="w-5 h-5" />
                Start Voice Assistant
              </>
            )}
          </button>
        </header>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          
          {/* Devices Panel */}
          <div className="lg:col-span-2 space-y-8">
            <section>
              <h2 className="text-lg font-medium text-zinc-300 mb-4 px-1">Lighting</h2>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <DeviceCard 
                  title="Living Room" 
                  icon={<Lightbulb className={devices['light.living_room'] ? "text-amber-400" : "text-zinc-500"} />}
                  isActive={devices['light.living_room']}
                  onClick={() => toggleDevice('light.living_room')}
                  stateText={devices['light.living_room'] ? 'On' : 'Off'}
                />
                <DeviceCard 
                  title="Kitchen" 
                  icon={<Lightbulb className={devices['light.kitchen'] ? "text-amber-400" : "text-zinc-500"} />}
                  isActive={devices['light.kitchen']}
                  onClick={() => toggleDevice('light.kitchen')}
                  stateText={devices['light.kitchen'] ? 'On' : 'Off'}
                />
              </div>
            </section>

            <section>
              <h2 className="text-lg font-medium text-zinc-300 mb-4 px-1">Climate</h2>
              <div className="grid grid-cols-1 gap-4">
                <div className="bg-zinc-900/50 border border-zinc-800/50 rounded-2xl p-6 flex items-center justify-between">
                  <div className="flex items-center gap-4">
                    <div className="w-12 h-12 rounded-full bg-orange-500/10 flex items-center justify-center">
                      <Thermostat className="w-6 h-6 text-orange-400" />
                    </div>
                    <div>
                      <h3 className="font-medium text-zinc-100">Living Room Thermostat</h3>
                      <p className="text-sm text-zinc-400">Target Temperature</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-4">
                    <button 
                      onClick={() => setDevices(p => ({...p, 'climate.living_room': p['climate.living_room'] - 1}))}
                      className="w-10 h-10 rounded-full bg-zinc-800 flex items-center justify-center hover:bg-zinc-700 transition-colors"
                    >-</button>
                    <span className="text-3xl font-light w-16 text-center">{devices['climate.living_room']}°</span>
                    <button 
                      onClick={() => setDevices(p => ({...p, 'climate.living_room': p['climate.living_room'] + 1}))}
                      className="w-10 h-10 rounded-full bg-zinc-800 flex items-center justify-center hover:bg-zinc-700 transition-colors"
                    >+</button>
                  </div>
                </div>
              </div>
            </section>

            <section>
              <h2 className="text-lg font-medium text-zinc-300 mb-4 px-1">Scenes</h2>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <button 
                  onClick={() => setDevices(prev => ({ ...prev, 'light.living_room': false, 'light.kitchen': false, 'climate.living_room': 68 }))}
                  className="bg-zinc-900/50 border border-zinc-800/50 hover:border-indigo-500/30 hover:bg-zinc-900 rounded-2xl p-5 flex items-center gap-4 transition-all text-left"
                >
                  <div className="w-10 h-10 rounded-full bg-indigo-500/10 flex items-center justify-center">
                    <Moon className="w-5 h-5 text-indigo-400" />
                  </div>
                  <div>
                    <h3 className="font-medium text-zinc-100">Goodnight</h3>
                    <p className="text-xs text-zinc-500">Lights off, Temp 68°</p>
                  </div>
                </button>
                <button 
                  onClick={() => setDevices(prev => ({ ...prev, 'light.living_room': false, 'light.kitchen': false, 'climate.living_room': 70 }))}
                  className="bg-zinc-900/50 border border-zinc-800/50 hover:border-purple-500/30 hover:bg-zinc-900 rounded-2xl p-5 flex items-center gap-4 transition-all text-left"
                >
                  <div className="w-10 h-10 rounded-full bg-purple-500/10 flex items-center justify-center">
                    <Film className="w-5 h-5 text-purple-400" />
                  </div>
                  <div>
                    <h3 className="font-medium text-zinc-100">Movie Time</h3>
                    <p className="text-xs text-zinc-500">Lights off, Temp 70°</p>
                  </div>
                </button>
              </div>
            </section>
          </div>

          {/* Assistant Transcript Panel */}
          <div className="bg-zinc-900/30 border border-zinc-800/50 rounded-3xl p-6 flex flex-col h-[600px]">
            <h2 className="text-lg font-medium text-zinc-100 mb-4 flex items-center gap-2">
              <Activity className="w-5 h-5 text-zinc-500" />
              Live Transcript
            </h2>
            
            <div className="flex-1 overflow-y-auto space-y-4 pr-2 custom-scrollbar">
              {transcripts.length === 0 ? (
                <div className="h-full flex flex-col items-center justify-center text-zinc-500 text-sm text-center space-y-4">
                  <Mic className="w-8 h-8 opacity-20" />
                  <p>Click "Start Voice Assistant" and try saying:<br/><br/>
                  "Turn on the living room light"<br/>
                  "Set the temperature to 72 degrees"<br/>
                  "Activate the Goodnight scene"</p>
                </div>
              ) : (
                transcripts.map((t, i) => (
                  <motion.div 
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    key={i} 
                    className={`p-4 rounded-2xl text-sm ${
                      t.role === 'user' 
                        ? 'bg-zinc-800 text-zinc-200 ml-8 rounded-tr-sm' 
                        : 'bg-indigo-500/10 text-indigo-200 border border-indigo-500/20 mr-8 rounded-tl-sm'
                    }`}
                  >
                    {t.text}
                  </motion.div>
                ))
              )}
              <div ref={transcriptEndRef} />
            </div>
            
            {isListening && (
              <div className="mt-4 pt-4 border-t border-zinc-800/50 flex items-center justify-center">
                <div className="flex gap-1 items-center h-4">
                  {[1, 2, 3, 4, 5].map((i) => (
                    <motion.div
                      key={i}
                      className="w-1 bg-indigo-500 rounded-full"
                      animate={{ height: ['20%', '100%', '20%'] }}
                      transition={{ 
                        repeat: Infinity, 
                        duration: 0.8, 
                        delay: i * 0.1,
                        ease: "easeInOut"
                      }}
                    />
                  ))}
                </div>
              </div>
            )}
          </div>

        </div>
      </div>
    </div>
  );
}

function DeviceCard({ title, icon, isActive, onClick, stateText }: { title: string, icon: React.ReactNode, isActive: boolean, onClick: () => void, stateText: string }) {
  return (
    <button 
      onClick={onClick}
      className={`relative overflow-hidden rounded-2xl p-6 transition-all duration-300 text-left border ${
        isActive 
          ? 'bg-zinc-800/80 border-zinc-700 shadow-lg' 
          : 'bg-zinc-900/40 border-zinc-800/50 hover:bg-zinc-900/80'
      }`}
    >
      <div className="flex items-start justify-between mb-4">
        <div className={`w-12 h-12 rounded-full flex items-center justify-center transition-colors ${
          isActive ? 'bg-amber-500/10' : 'bg-zinc-800'
        }`}>
          {icon}
        </div>
        <Power className={`w-5 h-5 transition-colors ${isActive ? 'text-amber-400' : 'text-zinc-600'}`} />
      </div>
      <h3 className="font-medium text-zinc-100 text-lg">{title}</h3>
      <p className={`text-sm mt-1 transition-colors ${isActive ? 'text-amber-400/80' : 'text-zinc-500'}`}>
        {stateText}
      </p>
    </button>
  );
}
