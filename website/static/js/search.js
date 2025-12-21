// search.js - Поиск в базе данных

document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('searchForm');
    const resetBtn = document.getElementById('resetBtn');
    
    form.addEventListener('submit', async function(e) {
        e.preventDefault();
        await performSearch();
    });
    
    resetBtn.addEventListener('click', function() {
        form.reset();
        document.getElementById('searchResults').innerHTML = '';
    });
});

async function performSearch() {
    const query = document.getElementById('query').value;
    const entity_name = document.getElementById('entity_name').value;
    const entity_type = document.getElementById('entity_type').value;
    const risk_level = document.getElementById('risk_level').value;
    const risk_category = document.getElementById('risk_category').value;
    const date_from = document.getElementById('date_from').value;
    const date_to = document.getElementById('date_to').value;
    
    // Построение URL с параметрами
    const params = new URLSearchParams();
    if (query) params.append('query', query);
    if (entity_name) params.append('entity_name', entity_name);
    if (entity_type) params.append('entity_type', entity_type);
    if (risk_level) params.append('risk_level', risk_level);
    if (risk_category) params.append('risk_category', risk_category);
    if (date_from) params.append('date_from', date_from);
    if (date_to) params.append('date_to', date_to);
    
    showLoading();
    
    try {
        const response = await fetch(`/api/v1/search?${params.toString()}`);
        
        if (!response.ok) {
            throw new Error('Ошибка поиска');
        }
        
        const data = await response.json();
        
        // Проверка статуса ответа
        if (data.status === 'database_unavailable') {
            showDatabaseError();
            return;
        }
        
        if (data.status === 'error') {
            showError(data.error || 'Произошла ошибка при поиске');
            return;
        }
        
        displaySearchResults(data);
    } catch (error) {
        console.error('Search error:', error);
        showError('Ошибка при выполнении поиска. Проверьте подключение к серверу.');
    } finally {
        hideLoading();
    }
}

function showDatabaseError() {
    const container = document.getElementById('searchResults');
    container.innerHTML = `
        <div class="alert alert-warning">
            <h5><i class="fas fa-database"></i> База данных не подключена</h5>
            <p class="mb-0">Функция поиска требует подключения к PostgreSQL. 
            Для использования поиска настройте базу данных согласно инструкции в README.md</p>
            <hr>
            <p class="mb-0"><strong>Вы можете:</strong></p>
            <ul>
                <li>Использовать функцию "Обработка текста" для анализа новостей в реальном времени</li>
                <li>Настроить PostgreSQL для полной функциональности</li>
            </ul>
        </div>
    `;
}

function displaySearchResults(data) {
    const container = document.getElementById('searchResults');
    
    if (!data.results || data.results.length === 0) {
        container.innerHTML = `
            <div class="alert alert-info">
                <i class="fas fa-info-circle"></i> 
                Ничего не найдено. Попробуйте изменить параметры поиска.
            </div>
        `;
        return;
    }
    
    let html = `
        <div class="card shadow-sm">
            <div class="card-header bg-primary text-white">
                <h5 class="mb-0">Результаты поиска: ${data.total} найдено</h5>
            </div>
            <div class="card-body">
    `;
    
    data.results.forEach((article, index) => {
        html += `
            <div class="result-item">
                <div class="result-header">
                    <h5>${article.title}</h5>
                    <div class="text-muted small">
                        ${article.source ? `<span><i class="fas fa-globe"></i> ${article.source}</span> | ` : ''}
                        <span><i class="fas fa-calendar"></i> ${formatDate(article.published_date)}</span>
                    </div>
                </div>
                
                <p class="text-muted">${truncateText(article.text, 200)}</p>
                
                ${article.entities && article.entities.length > 0 ? `
                    <div class="mb-2">
                        <strong>Сущности:</strong><br>
                        ${article.entities.slice(0, 10).map(e => 
                            `<span class="entity-badge entity-${e.type}">${e.text}</span>`
                        ).join(' ')}
                        ${article.entities.length > 10 ? `<span class="text-muted">+${article.entities.length - 10} еще</span>` : ''}
                    </div>
                ` : ''}
                
                ${article.risks && article.risks.length > 0 ? `
                    <div class="mb-2">
                        <strong>Риски:</strong><br>
                        ${article.risks.map(r => 
                            `<span class="risk-badge risk-${r.risk_level}">${r.category} (${r.risk_level})</span>`
                        ).join(' ')}
                    </div>
                ` : ''}
                
                <div class="mt-3">
                    <a href="#" class="btn btn-sm btn-outline-primary" onclick="viewArticleDetails('${article.article_id}'); return false;">
                        <i class="fas fa-eye"></i> Подробнее
                    </a>
                    ${article.url ? `<a href="${article.url}" target="_blank" class="btn btn-sm btn-outline-secondary">
                        <i class="fas fa-external-link-alt"></i> Источник
                    </a>` : ''}
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
        
        // Создать модальное окно с деталями (можно использовать Bootstrap Modal)
        alert('Детали статьи:\n\n' + JSON.stringify(article, null, 2));
    } catch (error) {
        console.error('Error:', error);
        alert('Ошибка загрузки статьи');
    }
}

function formatDate(dateString) {
    if (!dateString) return 'Дата неизвестна';
    const date = new Date(dateString);
    return date.toLocaleDateString('ru-RU');
}

function truncateText(text, maxLength) {
    if (!text) return '';
    if (text.length <= maxLength) return text;
    return text.substr(0, maxLength) + '...';
}

function showLoading() {
    document.getElementById('loadingContainer').style.display = 'block';
}

function hideLoading() {
    document.getElementById('loadingContainer').style.display = 'none';
}

function showError(message) {
    const container = document.getElementById('searchResults');
    container.innerHTML = `
        <div class="alert alert-danger">
            <i class="fas fa-exclamation-circle"></i> ${message}
        </div>
    `;
}
