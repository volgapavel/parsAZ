// process.js - Обработка текстов через API

document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('processForm');
    const dateInput = document.getElementById('date');
    const fetchBtn = document.getElementById('fetchBtn');
    
    // Установить текущую дату
    dateInput.valueAsDate = new Date();
    
    // Обработчик для кнопки извлечения контента из URL
    fetchBtn.addEventListener('click', async function() {
        await fetchFromUrl();
    });
    
    form.addEventListener('submit', async function(e) {
        e.preventDefault();
        await processText();
    });
});

async function fetchFromUrl() {
    const urlInput = document.getElementById('url');
    const url = urlInput.value.trim();
    
    if (!url) {
        showError('Введите URL статьи');
        return;
    }
    
    // Валидация URL
    try {
        new URL(url);
    } catch {
        showError('Введите корректный URL');
        return;
    }
    
    // Показать загрузку
    const fetchBtn = document.getElementById('fetchBtn');
    const originalText = fetchBtn.innerHTML;
    fetchBtn.disabled = true;
    fetchBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Загрузка...';
    hideError();
    
    try {
        const response = await fetch('/web-api/fetch-article', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ url: url })
        });
        
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || 'Ошибка загрузки статьи');
        }
        
        const data = await response.json();
        
        // Заполняем поля формы
        if (data.title) {
            document.getElementById('title').value = data.title;
        }
        if (data.text) {
            document.getElementById('text').value = data.text;
        }
        if (data.source) {
            document.getElementById('source').value = data.source;
        }
        if (data.published_date) {
            document.getElementById('date').value = data.published_date;
        }
        
        // Показываем уведомление об успехе
        showSuccess('Статья успешно загружена из URL');
        
    } catch (error) {
        console.error('Error:', error);
        showError('Не удалось загрузить статью: ' + error.message);
    } finally {
        fetchBtn.disabled = false;
        fetchBtn.innerHTML = originalText;
    }
}

async function processText() {
    const title = document.getElementById('title').value;
    const text = document.getElementById('text').value;
    const source = document.getElementById('source').value;
    const url = document.getElementById('url').value;
    const date = document.getElementById('date').value;
    
    // Валидация
    if (text.length < 50) {
        showError('Текст должен содержать минимум 50 символов');
        return;
    }
    
    // Показать загрузку
    showLoading();
    hideError();
    hideResults();
    
    try {
        const requestData = {
            title: title,
            text: text,
            source: source || null,
            url: url || null,
            published_date: date || null
        };
        
        const response = await fetch('/api/v1/process', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestData)
        });
        
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || 'Ошибка обработки текста');
        }
        
        const result = await response.json();
        displayResults(result);
    } catch (error) {
        console.error('Error:', error);
        showError(error.message);
    } finally {
        hideLoading();
    }
}

function displayResults(data) {
    const container = document.getElementById('processingResults');
    
    let html = `
        <div class="mb-4">
            <h5 class="border-bottom pb-2">Общая информация</h5>
            <p><strong>ID статьи:</strong> ${data.article_id || 'N/A'}</p>
            <p><strong>Заголовок:</strong> ${data.title}</p>
            <p><strong>Обработано:</strong> ${new Date().toLocaleString('ru-RU')}</p>
            <p><strong>Время обработки:</strong> ${data.processing_time_ms ? Math.round(data.processing_time_ms) + ' мс' : 'N/A'}</p>
        </div>
    `;
    
    // Сущности
    if (data.entities && typeof data.entities === 'object') {
        // Подсчет общего количества сущностей
        let totalEntities = 0;
        const entitiesByType = {};
        
        // Обработка структуры {persons: [...], organizations: [...], locations: [...]}
        for (const [type, entities] of Object.entries(data.entities)) {
            if (Array.isArray(entities) && entities.length > 0) {
                entitiesByType[type] = entities;
                totalEntities += entities.length;
            }
        }
        
        if (totalEntities > 0) {
            html += `
                <div class="mb-4">
                    <h5 class="border-bottom pb-2">
                        <i class="fas fa-tag text-primary"></i> 
                        Извлеченные сущности (${totalEntities})
                    </h5>
                    <div class="mt-3">
            `;
            
            // Маппинг типов на русские названия
            const typeNames = {
                'persons': 'Персоны',
                'organizations': 'Организации',
                'locations': 'Локации',
                'dates': 'Даты',
                'events': 'События',
                'positions': 'Должности',
                'all': 'Все сущности'
            };
            
            Object.keys(entitiesByType).forEach(type => {
                const displayName = typeNames[type] || type;
                html += `<div class="mb-2"><strong>${displayName}:</strong> `;
                entitiesByType[type].forEach(entity => {
                    const entityName = entity.name || entity.text;
                    html += `<span class="entity-badge entity-${type}">${entityName}</span> `;
                });
                html += `</div>`;
            });
            
            html += `</div></div>`;
        }
    }
    
    // Связи
    if (data.relationships && data.relationships.length > 0) {
        html += `
            <div class="mb-4">
                <h5 class="border-bottom pb-2">
                    <i class="fas fa-project-diagram text-info"></i> 
                    Выявленные связи (${data.relationships.length})
                </h5>
                <div class="mt-3">
        `;
        
        data.relationships.forEach(rel => {
            html += `
                <div class="relationship-item mb-3">
                    <div><strong>${rel.entity1_text}</strong> 
                    <span class="badge bg-info">${rel.relation_type}</span> 
                    <strong>${rel.entity2_text}</strong></div>
                    <small class="text-muted">Метод: ${rel.extraction_method} | Уверенность: ${(rel.confidence * 100).toFixed(1)}%</small>
                </div>
            `;
        });
        
        html += `</div></div>`;
    }
    
    // Риски
    if (data.risks && data.risks.length > 0) {
        html += `
            <div class="mb-4">
                <h5 class="border-bottom pb-2">
                    <i class="fas fa-exclamation-triangle text-danger"></i> 
                    Выявленные риски (${data.risks.length})
                </h5>
                <div class="mt-3">
        `;
        
        data.risks.forEach(risk => {
            html += `
                <div class="alert alert-${getRiskAlertClass(risk.risk_level)} mb-3">
                    <div class="d-flex justify-content-between align-items-start">
                        <div>
                            <h6 class="mb-1">
                                <span class="badge bg-secondary">${risk.category}</span>
                                <span class="risk-badge risk-${risk.risk_level}">${risk.risk_level.toUpperCase()}</span>
                            </h6>
                            <p class="mb-1"><strong>Сущность:</strong> ${risk.entity_text} (${risk.entity_type})</p>
                            <p class="mb-0"><small>${risk.description || 'Нет описания'}</small></p>
                        </div>
                        <div class="text-end">
                            <small class="text-muted">Уверенность: ${(risk.confidence * 100).toFixed(1)}%</small>
                        </div>
                    </div>
                </div>
            `;
        });
        
        html += `</div></div>`;
    }
    
    // Сводка
    // Подсчет количества сущностей
    let entitiesCount = 0;
    if (data.entities && typeof data.entities === 'object') {
        for (const entities of Object.values(data.entities)) {
            if (Array.isArray(entities)) {
                entitiesCount += entities.length;
            }
        }
    }
    
    // Подсчет рисков
    let risksCount = 0;
    if (data.risks && data.risks.detected_risks) {
        risksCount = data.risks.detected_risks.length;
    }
    
    html += `
        <div class="alert alert-info">
            <h6>Статистика обработки:</h6>
            <ul class="mb-0">
                <li>Сущностей извлечено: ${entitiesCount}</li>
                <li>Связей найдено: ${data.relationships?.length || 0}</li>
                <li>Рисков выявлено: ${risksCount}</li>
            </ul>
        </div>
    `;
    
    container.innerHTML = html;
    showResults();
}

function getRiskAlertClass(level) {
    const classes = {
        'none': 'success',
        'low': 'warning',
        'medium': 'warning',
        'high': 'danger',
        'critical': 'danger'
    };
    return classes[level] || 'info';
}

function showLoading() {
    document.getElementById('loadingContainer').style.display = 'block';
    document.getElementById('submitBtn').disabled = true;
}

function hideLoading() {
    document.getElementById('loadingContainer').style.display = 'none';
    document.getElementById('submitBtn').disabled = false;
}

function showResults() {
    document.getElementById('resultsContainer').style.display = 'block';
    document.getElementById('resultsContainer').scrollIntoView({ behavior: 'smooth' });
}

function hideResults() {
    document.getElementById('resultsContainer').style.display = 'none';
}

function showError(message) {
    const errorContainer = document.getElementById('errorContainer');
    document.getElementById('errorMessage').textContent = message;
    errorContainer.style.display = 'block';
    errorContainer.scrollIntoView({ behavior: 'smooth' });
}

function hideError() {
    document.getElementById('errorContainer').style.display = 'none';
}

function showSuccess(message) {
    // Создаем временное уведомление об успехе
    const alertDiv = document.createElement('div');
    alertDiv.className = 'alert alert-success alert-dismissible fade show mt-3';
    alertDiv.innerHTML = `
        <i class="fas fa-check-circle"></i> ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    const form = document.getElementById('processForm');
    form.parentElement.insertBefore(alertDiv, form);
    
    // Автоматически скрыть через 5 секунд
    setTimeout(() => {
        alertDiv.remove();
    }, 5000);
}
