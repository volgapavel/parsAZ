// entities.js - Просмотр сущностей

document.addEventListener('DOMContentLoaded', function() {
    loadEntities();
    
    const form = document.getElementById('filterForm');
    const resetBtn = document.getElementById('resetBtn');
    
    form.addEventListener('submit', function(e) {
        e.preventDefault();
        loadEntities();
    });
    
    resetBtn.addEventListener('click', function() {
        form.reset();
        loadEntities();
    });
});

async function loadEntities() {
    const entity_type = document.getElementById('entity_type_filter').value;
    const name = document.getElementById('name_filter').value;
    const limit = document.getElementById('limit').value;
    
    const params = new URLSearchParams();
    if (entity_type) params.append('entity_type', entity_type);
    if (name) params.append('name', name);
    if (limit) params.append('limit', limit);
    
    showLoading();
    
    try {
        const response = await fetch(`/api/v1/entities?${params.toString()}`);
        
        if (!response.ok) {
            throw new Error('Ошибка загрузки сущностей');
        }
        
        const data = await response.json();
        
        // Проверка статуса
        if (data.status === 'database_unavailable') {
            showDatabaseError();
            return;
        }
        
        displayEntities(data);
    } catch (error) {
        console.error('Error:', error);
        showError('Ошибка загрузки данных. Возможно, база данных не подключена.');
    } finally {
        hideLoading();
    }
}

function showDatabaseError() {
    const container = document.getElementById('entitiesResults');
    container.innerHTML = `
        <div class="alert alert-warning">
            <h5><i class="fas fa-database"></i> База данных не подключена</h5>
            <p class="mb-0">Функция просмотра сущностей требует подключения к PostgreSQL.</p>
            <hr>
            <p class="mb-0"><strong>Используйте функцию "Обработка текста"</strong> для извлечения сущностей из новостей в реальном времени.</p>
        </div>
    `;
}

function displayEntities(data) {
    const container = document.getElementById('entitiesResults');
    
    if (!data.entities || data.entities.length === 0) {
        container.innerHTML = `
            <div class="alert alert-info">
                <i class="fas fa-info-circle"></i> 
                Сущности не найдены.
            </div>
        `;
        return;
    }
    
    // Группировка по типам
    const grouped = {};
    data.entities.forEach(entity => {
        if (!grouped[entity.type]) {
            grouped[entity.type] = [];
        }
        grouped[entity.type].push(entity);
    });
    
    let html = `
        <div class="card shadow-sm mb-4">
            <div class="card-header bg-primary text-white">
                <h5 class="mb-0">Найдено сущностей: ${data.total}</h5>
            </div>
            <div class="card-body">
    `;
    
    Object.keys(grouped).forEach(type => {
        html += `
            <div class="mb-4">
                <h6 class="text-primary border-bottom pb-2">${type} (${grouped[type].length})</h6>
                <div class="row g-2">
        `;
        
        grouped[type].forEach(entity => {
            html += `
                <div class="col-md-6">
                    <div class="card">
                        <div class="card-body p-3">
                            <div class="d-flex justify-content-between align-items-start">
                                <div>
                                    <h6 class="mb-1">${entity.text}</h6>
                                    <span class="entity-badge entity-${entity.type}">${entity.type}</span>
                                </div>
                                <small class="text-muted">${entity.count || 1}x</small>
                            </div>
                            ${entity.article_id ? `
                                <div class="mt-2">
                                    <a href="#" class="btn btn-sm btn-outline-primary" 
                                       onclick="viewArticleDetails('${entity.article_id}'); return false;">
                                        <i class="fas fa-eye"></i> Статья
                                    </a>
                                </div>
                            ` : ''}
                        </div>
                    </div>
                </div>
            `;
        });
        
        html += `
                </div>
            </div>
        `;
    });
    
    html += `
            </div>
        </div>
    `;
    
    container.innerHTML = html;
}

async function viewArticleDetails(articleId) {
    try {
        const response = await fetch(`/api/v1/articles/${articleId}`);
        if (!response.ok) throw new Error('Статья не найдена');
        
        const article = await response.json();
        alert('Детали статьи:\n\n' + JSON.stringify(article, null, 2));
    } catch (error) {
        console.error('Error:', error);
        alert('Ошибка загрузки статьи');
    }
}

function showLoading() {
    document.getElementById('loadingContainer').style.display = 'block';
}

function hideLoading() {
    document.getElementById('loadingContainer').style.display = 'none';
}

function showError(message) {
    const container = document.getElementById('entitiesResults');
    container.innerHTML = `
        <div class="alert alert-danger">
            <i class="fas fa-exclamation-circle"></i> ${message}
        </div>
    `;
}
