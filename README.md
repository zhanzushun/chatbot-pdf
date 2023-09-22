
# 想法

- 基于 embedchain 做一个简单的界面
- 主要用来问答 pdf 和 mp3 文件
- 语音转文本使用 openai 的服务
- 代码尽量短小
- 流式输出
- 除了问答，还支持总结和普通聊天


## 前端 React

```
    npx create-react-app chatbot-pdf
    npm install axios react react-markdown
    npm install react-syntax-highlighter
    npm install react-router-dom
```

- 前端提供上传、选择文档、提问、聊天功能
- 支持 .mp3, .mp4, .m4a, .wav, .pdf, .docx, .doc, .txt
- 可选择多个文档提一个问题

## 后端 FastApi

- 使用自己的 PDF 解析工具 (embedchain 内置的 PDF 解析不太理想)
- 解析成 txt 之后使用 embedchain 进行存储及问答
- UI 界面上选择普通聊天还是问答
- 如果是问答，先用gpt4判断是否总结型，如果是，则传入整个文档做总结
- 否则使用 embedchain 进行问答


![...](screenshot.png)
