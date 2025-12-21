// stats.js - Статистика системы

let chartsInitialized = false;
let entitiesChart, risksChart, riskCategoriesChart;

document.addEventListener('DOMContentLoaded', function() {
    loadStats();
});

async function loadStats() {
    try {
        const response = await fetch('/api/v1/stats');
        
        if (!response.ok) {
            throw new Error('Ошибка загрузки статистики');
        }
        
        const data = await response.json();
        displayStats(data);
    } catch (error) {
        console.error('Error:', error);
        showError('Статистика недоступна. База данных не подключена.');
    } finally {
        hideLoading();
    }
}

function displayStats(data) {
    // Общие счетчики
    document.getElementById('total_articles').textContent = data.total_articles || 0;
    document.getElementById('total_entities').textContent = data.total_entities || 0;
    document.getElementById('total_relationships').textContent = data.total_relationships || 0;
    document.getElementById('total_risks').textContent = data.total_risks || 0;
    
    // График сущностей по типам
    if (data.entities_by_type && Object.keys(data.entities_by_type).length > 0) {
        createEntitiesChart(data.entities_by_type);
    }
    
    // График уровней рисков
    if (data.risks_by_level && Object.keys(data.risks_by_level).length > 0) {
        createRisksChart(data.risks_by_level);
    }
    
    // График категорий рисков
    if (data.risks_by_category && Object.keys(data.risks_by_category).length > 0) {
        createRiskCategoriesChart(data.risks_by_category);
    }
    
    // Топ источников
    if (data.top_sources) {
        displayTopSources(data.top_sources);
    }
    
    // Последние статьи
    if (data.recent_articles) {
        displayRecentArticles(data.recent_articles);
    }
}

function createEntitiesChart(data) {
    const ctx = document.getElementById('entitiesChart');
    if (!ctx) return;
    
    const labels = Object.keys(data);
    const values = Object.values(data);
    
    if (entitiesChart) {
        entitiesChart.destroy();
    }
    
    entitiesChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{
                data: values,
                backgroundColor: [
                    '#0d6efd', '#6610f2', '#6f42c1', '#d63384',
                    '#dc3545', '#fd7e14', '#ffc107', '#198754',
                    '#20c997', '#0dcaf0'
                ]
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    position: 'bottom'
                }
            }
        }
    });
}

function createRisksChart(data) {
    const ctx = document.getElementById('risksChart');
    if (!ctx) return;
    
    const labels = Object.keys(data).map(k => k.toUpperCase());
    const values = Object.values(data);
    
    const colors = {
        'NONE': '#198754',
        'LOW': '#ffc107',
        'MEDIUM': '#fd7e14',
        'HIGH': '#dc3545',
        'CRITICAL': '#842029'
    };
    
    if (risksChart) {
        risksChart.destroy();
    }
    
    risksChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Количество',
                data: values,
                backgroundColor: labels.map(l => colors[l] || '#6c757d')
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    display: false
                }
            },
            scales: {
                y: {
                    beginAtZero: true
                }
            }
        }
    });
}

function createRiskCategoriesChart(data) {
    const ctx = document.getElementById('riskCategoriesChart');
    if (!ctx) return;
    
    const labels = Object.keys(data);
    const values = Object.values(data);
    
    if (riskCategoriesChart) {
        riskCategoriesChart.destroy();
    }
    
    riskCategoriesChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Количество рисков',
                data: values,
                backgroundColor: '#dc3545'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            indexAxis: 'y',
            plugins: {
                legend: {
                    display: false
                }
            },
            scales: {
                x: {
                    beginAtZero: true
                }
            }
        }
    });
}

function displayTopSources(sources) {
    const container = document.getElementById('topSources');
    if (!container || !sources || sources.length === 0) {
        container.innerHTML = '<p class="text-muted">Нет данных</p>';
        return;
    }
    
    let html = '<ul class="list-group">';
    sources.forEach((source, index) => {
        html += `
            <li class="list-group-item d-flex justify-content-between align-items-center">
                <span>${index + 1}. ${source.source || 'Неизвестный источник'}</span>
                <span class="badge bg-primary rounded-pill">${source.count}</span>
            </li>
        `;
    });
    html += '</ul>';
    
    container.innerHTML = html;
}

function displayRecentArticles(articles) {
    const container = document.getElementById('recentArticles');
    if (!container || !articles || articles.length === 0) {
        container.innerHTML = '<p class="text-muted">Нет данных</p>';
        return;
    }
    
    let html = '<div class="list-group">';
    articles.forEach(article => {
        html += `
            <a href="#" class="list-group-item list-group-item-action" 
               onclick="viewArticle('${article.article_id}'); return false;">
                <div class="d-flex w-100 justify-content-between">
                    <h6 class="mb-1">${truncateText(article.title, 50)}</h6>
                    <small>${formatDate(article.published_date)}</small>
                </div>
                <small class="text-muted">${article.source || 'Источник неизвестен'}</small>
            </a>
        `;
    });
    html += '</div>';
    
    container.innerHTML = html;
}

function viewArticle(articleId) {
    window.location.href = `/search?article_id=${articleId}`;
}

function formatDate(dateString) {
    if (!dateString) return '';
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
    document.getElementById('statsContainer').style.display = 'none';
}

function hideLoading() {
    document.getElementById('loadingContainer').style.display = 'none';
    document.getElementById('statsContainer').style.display = 'block';
}

function showError(message) {
    hideLoading();
    document.getElementById('statsContainer').innerHTML = `
        <div class="alert alert-danger">
            <i class="fas fa-exclamation-circle"></i> ${message}
        </div>
    `;
}
