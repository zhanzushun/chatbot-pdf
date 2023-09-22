import React, { useState, useEffect } from 'react';

import ReactMarkdown from 'react-markdown';
import { handleStream } from './StreamUtil';
import { Light as SyntaxHighlighter } from 'react-syntax-highlighter';
import { docco } from 'react-syntax-highlighter/dist/esm/styles/hljs';
import './ChatBot.css'
import { getLocalStorage, setLocalStorage, emptyString } from './Util';
import { FileUpload } from './FileUpload';
import { API_HOST_PORT } from './Consts';


import { python } from 'react-syntax-highlighter/dist/esm/languages/hljs';
SyntaxHighlighter.registerLanguage('python', python);


const components = {
  code({ node, inline, className, children, ...props }) {
    const match = /language-(\w+)/.exec(className || '');
    const language = match && match[1] ? match[1] : 'javascript';
    return !inline && language ? (
      <SyntaxHighlighter language={language} style={docco} PreTag="div" customStyle={{ fontSize: '14px', backgroundColor: '#f6f6f6' }} {...props}>
        {String(children).replace(/\n$/, '')}
      </SyntaxHighlighter>
    ) : (
      <code className={className} {...props}>
        {children}
      </code>
    );
  },
};


const ChatMessage = ({ message, sender }) => {
  return (
    <div className={`chat-message ${sender}`}>
      <div className="message-bubble">
        <ReactMarkdown components={components} children={message} />
      </div>
      <div className="message-time">{new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}</div>
    </div>
  );
};


const fetchSendMessage = async (userInput, isNew, isAskDoc, fileIdList, onResponseWord) => {
  const headers = {
    'Authorization': `Bearer ${getLocalStorage('accessToken')}`,
    "Content-Type": "application/json"
  };
  
  let user = getLocalStorage('user')
  if (emptyString(user)){
    user = getLocalStorage('unionId') + (new Date().toISOString().slice(0, 10).replace(/-/g, ''))
  }

  var body = {
    user, 
    prompt: userInput
  }
  var stream_url = `${API_HOST_PORT}/api7/chat2_private_use`

  if (isAskDoc){
    body = {
      user,
      query: userInput,
      file_id_list: fileIdList
    }
    stream_url = `${API_HOST_PORT}/api7/askdoc`
  }

  handleStream(stream_url, body, headers,
    (tokenText) => {
      if (tokenText == null) { // 结束
        return
      }
      onResponseWord(tokenText)
    }
  )
}

const ChatInput = ({ onSend, onNew }) => {
  const [inputValue, setInputValue] = useState('');

  const handleSend = () => {
    if (inputValue.trim()) {
      onSend(inputValue, false);
      setInputValue('');
    }
  };
  const handleAskDoc = () => {
    if (inputValue.trim()) {
      onSend(inputValue, true);
      setInputValue('');
    }
  };

  const handleNew = () => {
    setLocalStorage('user', getLocalStorage('unionId') + '.' + (new Date().getTime()));
    onNew()
  }
  const vipBtnClass = 'button-vip'
  return (
    <div className="chat-input-container">
      <div className={`button ${vipBtnClass} new-button`} onClick={handleNew}>
        新话题
      </div>
      <textarea
        className="chat-input"
        value={inputValue}
        onChange={(e) => setInputValue(e.target.value)}
      />
      <div className={`button ${vipBtnClass} send-button`} onClick={handleSend}>
        聊天
      </div>
      <div className={`button ${vipBtnClass} send-button`} onClick={handleAskDoc}>
        文档问答
      </div>
    </div>
  );
};

const ChatBot = () => {

  const [messages, setMessages] = useState([]);
  const [isNew, setIsNew] = useState(false)
  const [fileIdList, setFileIdList] = useState('')

  useEffect(() => {
    if (document.body.scrollHeight <= window.innerHeight || messages.length == 0){
        return
    }
    window.scrollTo({
      top: document.body.scrollHeight - window.innerHeight + 20,
      behavior: 'smooth',
    });
  }, [messages]);

  const addMessage = (message, sender) => {
    setMessages((prevMessages) => [...prevMessages, { message, sender }]);
  };
  const updateMessage = (message, sender) => {
    setMessages((prevMessages) => [...prevMessages.slice(0, prevMessages.length - 1), { message, sender }]);
  };

  const handleSendMessage = async (input, isAskDoc) => {
    if (!input) return;
    addMessage(input, 'sent');
    let botResponse = '';
    await fetchSendMessage(input, isNew, isAskDoc, fileIdList, (word) => {
      if (botResponse === '') {
        botResponse += word
        addMessage(word, 'received')
      }
      else {
        botResponse += word;
        updateMessage(botResponse, 'received');
      }
    });
    setIsNew(false)
  };

  const handleFileIdList = (fileIdList) => {
    console.log('fileIdList=' + JSON.stringify(fileIdList))
    setFileIdList(fileIdList)
  }

  const handleNewBtn = () => {
    setIsNew(true)
    if (messages.length > 0){
      addMessage('------------------------新话题------------------------', 'sent')
    }
  }

  return (
    <div className="app-container">
      <div className="chat-section">
        <div className="chat-container">
          {messages.map((msg, index) => (
            <ChatMessage key={index} message={msg.message} sender={msg.sender} />
          ))}
        </div>
        <ChatInput onSend={handleSendMessage} onNew={handleNewBtn} />
      </div>
      <FileUpload onFileIdList={handleFileIdList}/>
    </div>)
};

export default ChatBot;
