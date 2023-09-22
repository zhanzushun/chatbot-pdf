import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './FileUpload.css'
import { API_HOST_PORT } from './Consts';

export const FileUpload = ({ onFileIdList }) => {
  // State for storing the list of uploaded files
  const [uploadedFiles, setUploadedFiles] = useState([]);
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [doing, setDoing] = useState(false);

  // Event handler for file upload
  const handleFileUpload = (event) => {
    // Create a new FormData object
    let formData = new FormData();

    // Add all selected files to the FormData object
    for (let file of event.target.files) {
      formData.append('files', file);
    }

    // Send a POST request to your backend service
    console.log('Uploading files...')
    setDoing(true)
    axios.post(`${API_HOST_PORT}/api7/uploadfile`, formData, {timeout: 1000*600})
      .then(response => {
        console.log(response.data);
        // After a successful upload, fetch the list of uploaded files again
        fetchUploadedFiles();
        setDoing(false)
      })
      .catch((error) => {
        console.error('Error:', error);
        window.alert(error)
        setDoing(false)
      });
  };

  // Function to fetch the list of uploaded files from the server
  const fetchUploadedFiles = () => {
    axios.post(`${API_HOST_PORT}/api7/getfiles`)
      .then(response => {
        setUploadedFiles(response.data);
      })
      .catch((error) => {
        console.error('Error:', error);
      });
  };

  const handleFileSelection = (event, timestamp) => {
    if (event.target.checked) {
      if (selectedFiles.length >= 10) {
        window.alert('目前只支持最多选择10个文档')
        return
      }
      setSelectedFiles(prevSelected => [...prevSelected, timestamp])
    } else {
      setSelectedFiles(prevSelected => prevSelected.filter(t => t !== timestamp))
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
        上传文件并生成词嵌入<br/>(耐心等待)</div>
      }

      <input type="file" id="fileInput" multiple onChange={handleFileUpload} style={{ display: 'none' }} />
      <div>.mp3, .mp4, .m4a, .wav, .pdf, .docx, .doc, .txt</div>

      {/* Section for document library */}
      <h2>文档库</h2>
      <ul className="file-list">
        {uploadedFiles.map((file, index) =>
          <li key={index}>
            <input type="checkbox" value={file.selected} onChange={event => handleFileSelection(event, file.timestamp)} />
            <span>{file.uploadtime} - {file.filename}</span>
          </li>
        )}
      </ul>
    </div>
  );
};
