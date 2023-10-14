import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './FileUpload.css'
import { API_HOST_PORT } from './Consts';

export const FileUpload = ({ onFileIdList }) => {
  // State for storing the list of uploaded files
  const [uploadedFiles, setUploadedFiles] = useState([]);
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [doing, setDoing] = useState(false);
  const [message, setMessage] = useState('上传文件并生成词嵌入');

  const handleFileUpload = async (event) => {
    let formData = new FormData();
    for (let file of event.target.files) {
      formData.append('files', file);
    }
    try {
      const response = await axios.post(`${API_HOST_PORT}/api7/uploadfile`, formData);
      const file_id = response.data.task_id;
      console.log('upload.response=' + JSON.stringify(response.data))
      if ('task_id' in response.data){
        const es = new EventSource(`${API_HOST_PORT}/api7/status/${file_id}`);
        es.onmessage = (event) => {
            if (event.data === "done") {
                setMessage((prevMessages) => '上传文件并生成词嵌入');
                es.close();
                setDoing(false)
                fetchUploadedFiles()
            }
            else {
              setMessage((prevMessages) => event.data);
            }
        };
      }
      else if ('filename' in response.data){
        window.alert('该文件已存在: ' + response.data.uploadtime + " " + response.data.filename)
      }
    } catch (error) {
        console.error("Error during the POST request:", error);
    }
  };

  const fetchUploadedFiles = () => {
    axios.post(`${API_HOST_PORT}/api7/getfiles`)
      .then(response => {
        setUploadedFiles(response.data);
      })
      .catch((error) => {
        console.error('Error:', error);
      });
  };

  const handleFileSelection = (event, file_id) => {
    if (event.target.checked) {
      if (selectedFiles.length >= 10) {
        window.alert('目前只支持最多选择10个文档')
        return
      }
      setSelectedFiles(prevSelected => [...prevSelected, file_id])
    } else {
      setSelectedFiles(prevSelected => prevSelected.filter(t => t !== file_id))
    }
  };

  // Fetch the list of uploaded files when the component is mounted
  useEffect(() => {
    fetchUploadedFiles();
  }, []);

  useEffect(() => {
    onFileIdList(selectedFiles);
  }, [selectedFiles, onFileIdList]);

  return (
    <div className="file-upload-container">
      {/* Button for uploading files */}
      { doing &&
        <div>处理中...</div>
      }
      { !doing && 
      <div className='button button-nonvip' onClick={() => document.getElementById('fileInput').click()}>
        {message}<br/>(耐心等待)</div>
      }

      <input type="file" id="fileInput" multiple onChange={handleFileUpload} style={{ display: 'none' }} />
      <div className="small-font">.mp3, .mp4, .m4a, .wav, .pdf, .docx, .doc, .ppt, .pptx, .txt, .png, .jpg, .jpeg</div>

      {/* Section for document library */}
      <h2>文档库</h2>
      <ul className="file-list small-font">
        {uploadedFiles.map((file, index) =>
          <li key={index}>
            <input type="checkbox" value={file.selected} onChange={event => handleFileSelection(event, file.file_id)} />
            <span><a href={file.url} target='_blank'>{file.uploadtime} - {file.filename}</a></span>
          </li>
        )}
      </ul>
    </div>
  );
};
