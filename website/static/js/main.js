// main.js - Скрипты для главной страницы

document.addEventListener('DOMContentLoaded', function() {
    loadQuickStats();
});

async function loadQuickStats() {
    try {
        const response = await fetch('/web-api/quick-stats');
        const data = await response.json();
        
        const statsHTML = `
            <div class="row g-3">
                <div class="col-6">
                    <div class="text-center">
                        <h4 class="text-primary mb-0">${data.total_articles || 0}</h4>
                        <small class="text-muted">Статей</small>
                    </div>
                </div>
                <div class="col-6">
                    <div class="text-center">
                        <h4 class="text-success mb-0">${data.total_entities || 0}</h4>
                        <small class="text-muted">Сущностей</small>
                    </div>
                </div>
                <div class="col-12">
                    <div class="text-center mt-2">
                        <h4 class="text-danger mb-0">${data.total_risks || 0}</h4>
                        <small class="text-muted">Рисков выявлено</small>
                    </div>
                </div>
            </div>
        `;
        
        document.getElementById('quick-stats').innerHTML = statsHTML;
    } catch (error) {
        console.error('Error loading stats:', error);
        document.getElementById('quick-stats').innerHTML = `
            <p class="text-muted text-center">Статистика недоступна</p>
            <p class="text-muted text-center small">База данных не подключена</p>
        `;
    }
}
