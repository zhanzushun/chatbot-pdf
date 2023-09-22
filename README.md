```
前端：

    npx create-react-app chatbot-pdf
    npm install axios react react-markdown
    npm install react-syntax-highlighter
    npm install react-router-dom

    前端提供上传、选择文档、提问、聊天功能
    可选择多个文档提一个问题

后端：

    - 使用自己的 PDF 解析工具 (embedchain 内置的 PDF 解析不太理想)
    - 解析成 txt 之后使用 embedchain 进行存储及问答
    - UI 界面上选择普通聊天还是问答
    - 如果是问答，先用gpt4判断是否总结型，如果是，则传入整个文档做总结
    - 否则使用 embedchain 进行问答

```