import React, { useState, useEffect, useRef } from 'react';

const StreamData = () => {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const wsRef = useRef(null);

  useEffect(() => {
    const websocket = new WebSocket('ws://localhost:8765');
    wsRef.current = websocket;

    websocket.onopen = () => console.log('Connected to WebSocket server');
    websocket.onmessage = (event) => {
      setMessages((prevMessages) => [...prevMessages, event.data]);
    };
    websocket.onclose = () => console.log('Disconnected from WebSocket server');

    return () => websocket.close();
  }, []);

  const sendMessage = () => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(input);
      setInput('');
    }
  };

  return (
    <div className="p-5 border border-neutral-300 rounded-lg w-[300px] mx-auto">
      <h2 className="text-lg font-semibold mb-3">Real-Time Notifications</h2>
      <div className="max-h-[200px] overflow-y-auto border border-neutral-200 p-2.5 mb-2.5 rounded">
        {messages.map((message, index) => (
          <p key={index}>{message}</p>
        ))}
      </div>
      <input
        type="text"
        value={input}
        onChange={(e) => setInput(e.target.value)}
        placeholder="Type a message"
        className="w-full p-2 mt-1 border border-neutral-300 rounded"
      />
      <button
        onClick={sendMessage}
        className="w-full p-2.5 mt-2.5 bg-blue-600 text-white border-none cursor-pointer rounded-md hover:bg-blue-700 transition-colors"
      >
        Send
      </button>
    </div>
  );
};

export default StreamData;