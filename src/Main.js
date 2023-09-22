import React, { useState, useEffect } from 'react';

import ChatBot from './ChatBot'

const Main = () => {

  return (
    <div>
        <div className="title-container">
          <h1 className="title"><span style={{ cursor: 'pointer' }}>🤖 GPT4 - VIP</span></h1>
        </div>

      <ChatBot />
    </div>)
};

export default Main;
