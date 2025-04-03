document.addEventListener('DOMContentLoaded', function() {
    const dropZone = document.getElementById('dropZone');
    const fileInput = document.getElementById('csvFile');
    const fileInfo = document.getElementById('fileInfo');
    let currentUpload = null;

    // Получаем обязательные поля из data-атрибута
    const requiredFields = dropZone && dropZone.dataset.requiredFields ? 
        dropZone.dataset.requiredFields.split(',').filter(Boolean) : [];

    // Обработчики для drag-and-drop
    if (dropZone) {
        dropZone.addEventListener('dragover', function(e) {
            e.preventDefault();
            dropZone.classList.add('border-primary');
        });

        dropZone.addEventListener('dragleave', function() {
            dropZone.classList.remove('border-primary');
        });

        dropZone.addEventListener('drop', function(e) {
            e.preventDefault();
            dropZone.classList.remove('border-primary');
            const file = e.dataTransfer.files[0];
            handleFile(file);
        });
    }

    // Обработчик для выбора файла через кнопку
    if (fileInput) {
        fileInput.addEventListener('change', function() {
            if (this.files.length > 0) {
                handleFile(this.files[0]);
            }
        });
    }

    function handleFile(file) {
        // Проверяем тип файла
        if (!file.name.endsWith('.csv')) {
            showError('Пожалуйста, выберите CSV файл');
            return;
        }

        // Проверяем размер файла (10 МБ)
        if (file.size > 10 * 1024 * 1024) {
            showError('Размер файла не должен превышать 10 МБ');
            return;
        }

        // Показываем информацию о файле
        document.getElementById('fileName').textContent = file.name;
        document.getElementById('fileSize').textContent = formatFileSize(file.size);
        document.getElementById('fileType').textContent = file.type;
        fileInfo.style.display = 'block';

        // Читаем файл для предпросмотра
        const reader = new FileReader();
        reader.onload = function(e) {
            const preview = parseCSV(e.target.result);
            showPreview(preview);
            if (preview.isValid) {
                uploadFile(file);
            }
        };
        reader.readAsText(file);
    }

    function formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    function parseCSV(content) {
        const lines = content.split('\n').slice(0, 6); // Берем первые 5 строк для предпросмотра
        const headers = lines[0].split(',').map(h => h.trim());
        
        // Проверяем наличие всех обязательных полей
        const missingFields = requiredFields.filter(field => !headers.includes(field));
        
        return {
            headers: headers,
            rows: lines.slice(1).map(line => line.split(',')),
            isValid: missingFields.length === 0,
            missingFields: missingFields
        };
    }

    function showPreview(preview) {
        const previewCard = document.getElementById('previewCard');
        const previewHeader = document.getElementById('previewHeader');
        const previewBody = document.getElementById('previewBody');

        // Показываем предпросмотр
        previewCard.style.display = 'block';

        // Заполняем заголовки
        previewHeader.innerHTML = `
            <tr>
                ${preview.headers.map(h => `<th>${h}</th>`).join('')}
            </tr>
        `;

        // Заполняем данные
        previewBody.innerHTML = preview.rows
            .map(row => `
                <tr>
                    ${row.map(cell => `<td>${cell}</td>`).join('')}
                </tr>
            `)
            .join('');

        // Показываем ошибки, если есть
        if (!preview.isValid) {
            showError(`Отсутствуют обязательные поля: ${preview.missingFields.join(', ')}`);
        }
    }

    function uploadFile(file) {
        // Сбрасываем предыдущие результаты перед новой загрузкой
        document.getElementById('importResults').style.display = 'none';
        document.getElementById('importErrors').style.display = 'none';

        const formData = new FormData();
        formData.append('file', file);
        formData.append('csrfmiddlewaretoken', getCookie('csrftoken'));

        const xhr = new XMLHttpRequest();
        currentUpload = xhr;

        // Настраиваем отображение прогресса
        const progressBar = document.getElementById('progressBar');
        const progressPercent = document.getElementById('progressPercent');
        const uploadProgress = document.getElementById('uploadProgress'); 
        uploadProgress.style.display = 'block';

        xhr.upload.onprogress = function(e) {
            if (e.lengthComputable) {
                const percentComplete = (e.loaded / e.total) * 100;
                progressBar.style.width = percentComplete + '%';
                progressPercent.textContent = percentComplete.toFixed(1) + '%';
            }
        };

        xhr.onload = function() {
            // Скрываем прогресс загрузки после получения ответа
            uploadProgress.style.display = 'none';
            
            try {
                const response = JSON.parse(xhr.responseText);
                
                if (xhr.status === 200) {
                    showResults(response);
                } else {
                    showError(response.error || `Ошибка сервера: ${xhr.status}`);
                    console.error('Server error:', response);
                }
            } catch (e) {
                showError(`Ошибка при обработке ответа: ${e.message}`);
                console.error('Error parsing response:', xhr.responseText, e);
            }
        };

        xhr.onerror = function() {
            uploadProgress.style.display = 'none';
            showError('Ошибка сети при загрузке файла');
        };

        xhr.onabort = function() {
            uploadProgress.style.display = 'none';
            showError('Загрузка была прервана');
        };

        xhr.open('POST', window.location.pathname, true);
        xhr.send(formData);

        // Добавляем кнопку отмены
        const cancelButton = document.createElement('button');
        cancelButton.className = 'btn btn-sm btn-danger mt-2';
        cancelButton.textContent = 'Отменить загрузку';
        cancelButton.onclick = function() {
            if (currentUpload) {
                currentUpload.abort();
            }
        };
        
        // Удаляем предыдущие кнопки отмены, если есть
        const existingButtons = uploadProgress.querySelectorAll('button');
        existingButtons.forEach(button => button.remove());
        
        uploadProgress.appendChild(cancelButton);
    }

    function showResults(response) {
        const results = document.getElementById('importResults');
        const errors = document.getElementById('importErrors');
        
        // Показываем результаты
        document.getElementById('processedRows').textContent = response.processed || 0;
        document.getElementById('successRows').textContent = response.success_count || 0;
        document.getElementById('errorRows').textContent = response.error_count || 0;
        results.style.display = 'block';

        // Показываем ошибки, если есть
        if (response.errors && response.errors.length > 0) {
            const errorList = document.getElementById('errorList');
            errorList.innerHTML = response.errors
                .map(error => `<li>${error}</li>`)
                .join('');
            errors.style.display = 'block';
        }

        // Обновляем таблицу с данными, если нужно
        if (response.success_count > 0) {
            // Здесь можно добавить код для обновления основной таблицы
            // или показать сообщение о необходимости обновить страницу
            setTimeout(() => {
                window.location.reload();
            }, 3000);
        }
    }

    function showError(message) {
        const errors = document.getElementById('importErrors');
        const errorList = document.getElementById('errorList');
        errorList.innerHTML = `<li>${message}</li>`;
        errors.style.display = 'block';
    }

    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }
}); 