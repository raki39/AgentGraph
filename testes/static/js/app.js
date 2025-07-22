// Sistema de Testes Massivos - JavaScript
class TestManager {
    constructor() {
        this.sessionId = null;
        this.groups = [];
        this.isRunning = false;
        this.statusInterval = null;
        
        this.initializeEventListeners();
    }
    
    initializeEventListeners() {
        // Criar sessão
        document.getElementById('createSession').addEventListener('click', () => {
            this.createSession();
        });
        
        // Toggle Processing Agent
        document.getElementById('enableProcessing').addEventListener('change', (e) => {
            const processingDiv = document.getElementById('processingModelDiv');
            processingDiv.style.display = e.target.checked ? 'block' : 'none';
        });
        
        // Toggle método de validação
        document.getElementById('validationMethod').addEventListener('change', (e) => {
            const keywordDiv = document.getElementById('keywordDiv');
            keywordDiv.style.display = e.target.value === 'keyword' ? 'block' : 'none';
        });
        
        // Adicionar grupo
        document.getElementById('addGroup').addEventListener('click', () => {
            this.addGroup();
        });
        
        // Executar testes
        document.getElementById('runTests').addEventListener('click', () => {
            this.runTests();
        });
        
        // Download CSV
        document.getElementById('downloadCsv').addEventListener('click', () => {
            this.downloadCsv();
        });
    }
    
    async createSession() {
        const question = document.getElementById('testQuestion').value.trim();
        
        if (!question) {
            this.showAlert('Por favor, digite uma pergunta para o teste.', 'warning');
            return;
        }
        
        try {
            const response = await fetch('/api/create_test_session', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ question })
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.sessionId = data.session_id;
                this.showSessionInfo(question);
                this.showAlert('Sessão criada com sucesso!', 'success');
                
                // Mostra configuração de grupo
                document.getElementById('groupConfig').style.display = 'block';
                document.getElementById('validationConfig').style.display = 'block';
                
                // Desabilita criação de nova sessão
                document.getElementById('createSession').disabled = true;
                document.getElementById('testQuestion').disabled = true;
                
            } else {
                this.showAlert(data.error, 'danger');
            }
        } catch (error) {
            this.showAlert('Erro ao criar sessão: ' + error.message, 'danger');
        }
    }
    
    showSessionInfo(question) {
        const sessionInfo = document.getElementById('sessionInfo');
        const sessionDetails = document.getElementById('sessionDetails');
        
        sessionDetails.innerHTML = `
            <strong>ID:</strong> ${this.sessionId}<br>
            <strong>Pergunta:</strong> ${question}<br>
            <strong>Criado em:</strong> ${new Date().toLocaleString()}
        `;
        
        sessionInfo.style.display = 'block';
    }
    
    async addGroup() {
        const sqlModel = document.getElementById('sqlModel').value;
        const processingEnabled = document.getElementById('enableProcessing').checked;
        const processingModel = processingEnabled ? document.getElementById('processingModel').value : null;
        const iterations = parseInt(document.getElementById('iterations').value);
        
        if (iterations < 1 || iterations > 100) {
            this.showAlert('Número de iterações deve ser entre 1 e 100.', 'warning');
            return;
        }
        
        try {
            const response = await fetch('/api/add_test_group', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    sql_model: sqlModel,
                    processing_enabled: processingEnabled,
                    processing_model: processingModel,
                    iterations: iterations
                })
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.groups.push(data.group);
                this.updateGroupsList();
                this.showAlert(`Grupo ${data.group.id} adicionado com sucesso!`, 'success');
                
                // Reset form
                document.getElementById('iterations').value = 5;
                document.getElementById('enableProcessing').checked = false;
                document.getElementById('processingModelDiv').style.display = 'none';
                
            } else {
                this.showAlert(data.error, 'danger');
            }
        } catch (error) {
            this.showAlert('Erro ao adicionar grupo: ' + error.message, 'danger');
        }
    }
    
    updateGroupsList() {
        const groupsList = document.getElementById('groupsList');
        
        if (this.groups.length === 0) {
            groupsList.innerHTML = '<p class="text-muted">Nenhum grupo configurado ainda.</p>';
            return;
        }
        
        let html = '';
        this.groups.forEach(group => {
            html += `
                <div class="test-group-card">
                    <div class="d-flex justify-content-between align-items-center">
                        <div>
                            <h6><i class="fas fa-cog"></i> Grupo ${group.id}</h6>
                            <small class="text-muted">
                                <strong>SQL:</strong> ${group.sql_model_name}<br>
                                <strong>Processing:</strong> ${group.processing_enabled ? group.processing_model_name : 'Desativado'}<br>
                                <strong>Iterações:</strong> ${group.iterations}
                            </small>
                        </div>
                        <div class="text-end">
                            <span class="badge bg-primary">${group.iterations} testes</span>
                        </div>
                    </div>
                </div>
            `;
        });
        
        groupsList.innerHTML = html;
    }
    
    async runTests() {
        if (this.groups.length === 0) {
            this.showAlert('Adicione pelo menos um grupo de teste.', 'warning');
            return;
        }
        
        const validationMethod = document.getElementById('validationMethod').value;
        const expectedContent = document.getElementById('expectedContent').value;
        
        if (validationMethod === 'keyword' && !expectedContent.trim()) {
            this.showAlert('Digite o conteúdo esperado para validação por palavra-chave.', 'warning');
            return;
        }
        
        try {
            const response = await fetch('/api/run_tests', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    validation_method: validationMethod,
                    expected_content: expectedContent
                })
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.isRunning = true;
                this.updateStatus('running');
                this.showProgressContainer();
                this.startStatusPolling();
                this.showAlert('Testes iniciados com sucesso!', 'success');
                
                // Desabilita controles
                document.getElementById('addGroup').disabled = true;
                document.getElementById('runTests').disabled = true;
                
            } else {
                this.showAlert(data.error, 'danger');
            }
        } catch (error) {
            this.showAlert('Erro ao executar testes: ' + error.message, 'danger');
        }
    }
    
    showProgressContainer() {
        document.getElementById('progressContainer').style.display = 'block';
    }
    
    startStatusPolling() {
        this.statusInterval = setInterval(() => {
            this.checkTestStatus();
        }, 2000); // Verifica a cada 2 segundos
    }
    
    async checkTestStatus() {
        try {
            const response = await fetch('/api/test_status');
            const data = await response.json();

            if (data.success) {
                const status = data.status;

                // Atualiza progresso
                this.updateProgress(status);

                // Log para debug
                console.log('Status atual:', status.status, 'Progresso:', status.progress);

                // Verifica se terminou
                if (status.status === 'completed') {
                    this.isRunning = false;
                    this.updateStatus('completed');
                    clearInterval(this.statusInterval);
                    this.statusInterval = null;

                    console.log('✅ Testes concluídos, carregando resultados...');
                    await this.loadResults();
                    this.showAlert('Testes concluídos com sucesso!', 'success');

                    // Reabilita controles
                    document.getElementById('addGroup').disabled = false;
                    document.getElementById('runTests').disabled = false;

                } else if (status.status === 'error') {
                    this.isRunning = false;
                    this.updateStatus('error');
                    clearInterval(this.statusInterval);
                    this.statusInterval = null;
                    this.showAlert('Erro durante execução dos testes.', 'danger');

                    // Reabilita controles
                    document.getElementById('addGroup').disabled = false;
                    document.getElementById('runTests').disabled = false;
                }
            } else {
                console.error('Erro na resposta do status:', data.error);
            }
        } catch (error) {
            console.error('Erro ao verificar status:', error);
            // Para o polling em caso de erro persistente
            if (this.statusInterval) {
                clearInterval(this.statusInterval);
                this.statusInterval = null;
                this.showAlert('Erro de comunicação com o servidor.', 'danger');
            }
        }
    }
    
    updateProgress(status) {
        const progressBar = document.getElementById('progressBar');
        const completedTests = document.getElementById('completedTests');
        const totalTests = document.getElementById('totalTests');
        const currentGroup = document.getElementById('currentGroup');
        const estimatedTime = document.getElementById('estimatedTime');

        progressBar.style.width = status.progress + '%';
        progressBar.textContent = Math.round(status.progress) + '%';

        completedTests.textContent = status.completed_tests;
        totalTests.textContent = status.total_tests;
        currentGroup.textContent = status.current_group || '-';

        if (status.estimated_remaining) {
            const minutes = Math.floor(status.estimated_remaining / 60);
            const seconds = Math.floor(status.estimated_remaining % 60);
            estimatedTime.textContent = `${minutes}m ${seconds}s`;
        } else {
            estimatedTime.textContent = '-';
        }

        // Atualiza informações de testes em execução
        this.updateRunningTests(status);
    }

    updateRunningTests(status) {
        const currentTestDetails = document.getElementById('currentTestDetails');
        const runningTestsCount = document.getElementById('runningTestsCount');
        const runningTestsList = document.getElementById('runningTestsList');
        const runningTestsContainer = document.getElementById('runningTestsContainer');

        // Atualiza contador
        const runningCount = status.running_tests_count || 0;
        runningTestsCount.textContent = runningCount;
        runningTestsCount.className = runningCount > 0 ? 'badge bg-primary' : 'badge bg-secondary';

        // Atualiza teste atual
        if (status.current_test) {
            currentTestDetails.innerHTML = `
                <span class="badge bg-info">${status.current_test}</span>
                <small class="text-muted d-block">Teste em execução</small>
            `;
        } else {
            currentTestDetails.innerHTML = '<span class="text-muted">Nenhum teste em execução</span>';
        }

        // Atualiza lista de testes em execução
        if (runningCount > 0 && status.running_tests) {
            runningTestsList.style.display = 'block';
            runningTestsContainer.innerHTML = '';

            status.running_tests.forEach(test => {
                const duration = Math.floor((Date.now() / 1000) - test.start_time);
                const minutes = Math.floor(duration / 60);
                const seconds = duration % 60;

                const testElement = document.createElement('div');
                testElement.className = 'list-group-item d-flex justify-content-between align-items-center';
                testElement.innerHTML = `
                    <div>
                        <strong>Grupo ${test.group_id}</strong> - Iteração ${test.iteration}
                        <br><small class="text-muted">${test.question}</small>
                    </div>
                    <div class="text-end">
                        <span class="badge bg-warning">${minutes}m ${seconds}s</span>
                        <button class="btn btn-sm btn-outline-danger ms-2" onclick="testManager.cancelSpecificTest('${test.thread_id}')">
                            <i class="fas fa-times"></i>
                        </button>
                    </div>
                `;
                runningTestsContainer.appendChild(testElement);
            });
        } else {
            runningTestsList.style.display = 'none';
        }

        // Habilita/desabilita botões
        const hasRunningTests = runningCount > 0;
        document.getElementById('cancelCurrentBtn').disabled = !hasRunningTests;
        document.getElementById('cancelAllBtn').disabled = !hasRunningTests;
        document.getElementById('skipStuckBtn').disabled = !hasRunningTests;
    }

    async cancelCurrentTest() {
        try {
            const response = await fetch('/api/cancel_test', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });

            const data = await response.json();

            if (data.success) {
                this.showAlert(data.message, 'success');
            } else {
                this.showAlert(data.error, 'danger');
            }
        } catch (error) {
            this.showAlert('Erro ao cancelar teste: ' + error.message, 'danger');
        }
    }

    async cancelSpecificTest(threadId) {
        try {
            const response = await fetch('/api/cancel_test', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ thread_id: threadId })
            });

            const data = await response.json();

            if (data.success) {
                this.showAlert(data.message, 'success');
            } else {
                this.showAlert(data.error, 'danger');
            }
        } catch (error) {
            this.showAlert('Erro ao cancelar teste específico: ' + error.message, 'danger');
        }
    }

    async cancelAllTests() {
        if (!confirm('Tem certeza que deseja cancelar TODOS os testes em execução?')) {
            return;
        }

        try {
            const response = await fetch('/api/cancel_all_tests', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });

            const data = await response.json();

            if (data.success) {
                this.showAlert(data.message, 'warning');
            } else {
                this.showAlert(data.error, 'danger');
            }
        } catch (error) {
            this.showAlert('Erro ao cancelar todos os testes: ' + error.message, 'danger');
        }
    }

    async skipStuckTests() {
        try {
            const response = await fetch('/api/skip_stuck_tests', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ max_duration: 120 })
            });

            const data = await response.json();

            if (data.success) {
                this.showAlert(data.message, 'info');
            } else {
                this.showAlert(data.error, 'danger');
            }
        } catch (error) {
            this.showAlert('Erro ao pular testes travados: ' + error.message, 'danger');
        }
    }
    
    async loadResults() {
        try {
            console.log('🔄 Carregando resultados...');
            const response = await fetch('/api/test_results');
            const data = await response.json();

            console.log('📊 Resposta dos resultados:', data);

            if (data.success) {
                console.log('✅ Resultados carregados, exibindo...');
                this.displayResults(data.results);
                document.getElementById('resultsContainer').style.display = 'block';
                console.log('✅ Interface de resultados exibida');
            } else {
                console.error('❌ Erro nos resultados:', data.error);
                this.showAlert('Erro ao carregar resultados: ' + data.error, 'danger');
            }
        } catch (error) {
            console.error('❌ Erro ao carregar resultados:', error);
            this.showAlert('Erro ao carregar resultados: ' + error.message, 'danger');
        }
    }
    
    displayResults(results) {
        this.displaySummary(results.summary);
        this.displayGroupResults(results.group_results);
        this.displayIndividualResults(results.individual_results);
    }
    
    displaySummary(summary) {
        const summaryContent = document.getElementById('summaryContent');
        
        summaryContent.innerHTML = `
            <div class="row">
                <div class="col-md-3">
                    <div class="metric-card">
                        <div class="metric-value">${summary.total_tests}</div>
                        <div class="metric-label">Total de Testes</div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="metric-card">
                        <div class="metric-value">${summary.overall_success_rate}%</div>
                        <div class="metric-label">Taxa de Sucesso</div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="metric-card">
                        <div class="metric-value">${summary.overall_validation_rate}%</div>
                        <div class="metric-label">Taxa de Validação</div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="metric-card">
                        <div class="metric-value">${summary.avg_response_consistency}%</div>
                        <div class="metric-label">Consistência Média</div>
                    </div>
                </div>
            </div>
            
            <div class="row mt-4">
                <div class="col-md-6">
                    <h6>🏆 Melhor Grupo (Validação)</h6>
                    <div class="card">
                        <div class="card-body">
                            <strong>Grupo ${summary.best_performing_group.group_id}</strong><br>
                            <small>
                                ${summary.best_performing_group.group_config.sql_model_name}<br>
                                Processing: ${summary.best_performing_group.group_config.processing_enabled ? 'Ativo' : 'Inativo'}<br>
                                Taxa: ${summary.best_performing_group.validation_rate}%
                            </small>
                        </div>
                    </div>
                </div>
                <div class="col-md-6">
                    <h6>🎯 Grupo Mais Consistente</h6>
                    <div class="card">
                        <div class="card-body">
                            <strong>Grupo ${summary.most_consistent_group.group_id}</strong><br>
                            <small>
                                ${summary.most_consistent_group.group_config.sql_model_name}<br>
                                Processing: ${summary.most_consistent_group.group_config.processing_enabled ? 'Ativo' : 'Inativo'}<br>
                                Consistência: ${summary.most_consistent_group.response_consistency}%
                            </small>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }
    
    displayGroupResults(groupResults) {
        const groupsContent = document.getElementById('groupsContent');
        
        let html = '<div class="table-responsive"><table class="table table-striped"><thead><tr>';
        html += '<th>Grupo</th><th>Modelo SQL</th><th>Processing</th><th>Testes</th>';
        html += '<th>Sucesso</th><th>Validação</th><th>Consistência</th><th>Tempo Médio</th>';
        html += '</tr></thead><tbody>';
        
        groupResults.forEach(group => {
            const config = group.group_config;
            html += `
                <tr>
                    <td><strong>${group.group_id}</strong></td>
                    <td>${config.sql_model_name}</td>
                    <td>${config.processing_enabled ? config.processing_model_name : 'Não'}</td>
                    <td>${group.total_tests}</td>
                    <td><span class="badge bg-${group.success_rate >= 80 ? 'success' : group.success_rate >= 60 ? 'warning' : 'danger'}">${group.success_rate}%</span></td>
                    <td><span class="badge bg-${group.validation_rate >= 80 ? 'success' : group.validation_rate >= 60 ? 'warning' : 'danger'}">${group.validation_rate}%</span></td>
                    <td>${group.response_consistency}%</td>
                    <td>${group.avg_execution_time}s</td>
                </tr>
            `;
        });
        
        html += '</tbody></table></div>';
        groupsContent.innerHTML = html;
    }
    
    displayIndividualResults(individualResults) {
        const individualContent = document.getElementById('individualContent');
        
        let html = '<div class="table-responsive"><table class="table table-sm"><thead><tr>';
        html += '<th>Grupo</th><th>Iter.</th><th>Modelo</th><th>Sucesso</th><th>Validação</th><th>Tempo</th><th>Ações</th>';
        html += '</tr></thead><tbody>';
        
        individualResults.slice(0, 100).forEach((result, index) => { // Limita a 100 para performance
            const validation = result.validation || {};
            html += `
                <tr>
                    <td>${result.group_id}</td>
                    <td>${result.iteration}</td>
                    <td><small>${result.sql_model}</small></td>
                    <td><span class="badge bg-${result.success ? 'success' : 'danger'}">${result.success ? 'Sim' : 'Não'}</span></td>
                    <td><span class="badge bg-${validation.valid ? 'success' : 'danger'}">${validation.score || 0}</span></td>
                    <td>${result.execution_time}s</td>
                    <td><button class="btn btn-sm btn-outline-info" onclick="testManager.showResultDetails(${index})">Ver</button></td>
                </tr>
            `;
        });
        
        html += '</tbody></table></div>';
        
        if (individualResults.length > 100) {
            html += `<p class="text-muted mt-2">Mostrando primeiros 100 de ${individualResults.length} resultados. Baixe o CSV para ver todos.</p>`;
        }
        
        individualContent.innerHTML = html;
        
        // Armazena resultados para detalhes
        this.individualResults = individualResults;
    }
    
    showResultDetails(index) {
        const result = this.individualResults[index];
        const validation = result.validation || {};
        
        const modal = `
            <div class="modal fade" id="resultModal" tabindex="-1">
                <div class="modal-dialog modal-lg">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">Detalhes do Teste - Grupo ${result.group_id}, Iteração ${result.iteration}</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <h6>Configuração</h6>
                            <p><strong>Modelo SQL:</strong> ${result.sql_model}<br>
                            <strong>Processing Agent:</strong> ${result.processing_enabled ? result.processing_model : 'Desativado'}<br>
                            <strong>Tempo de Execução:</strong> ${result.execution_time}s</p>
                            
                            <h6>Query SQL</h6>
                            <pre class="bg-light p-2"><code>${result.sql_query || 'N/A'}</code></pre>
                            
                            <h6>Resposta</h6>
                            <div class="bg-light p-2" style="max-height: 200px; overflow-y: auto;">
                                ${result.response || 'N/A'}
                            </div>
                            
                            <h6>Validação</h6>
                            <p><strong>Válida:</strong> ${validation.valid ? 'Sim' : 'Não'}<br>
                            <strong>Pontuação:</strong> ${validation.score || 0}<br>
                            <strong>Razão:</strong> ${validation.reason || 'N/A'}</p>
                            
                            ${result.error ? `<h6>Erro</h6><div class="alert alert-danger">${result.error}</div>` : ''}
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        // Remove modal anterior se existir
        const existingModal = document.getElementById('resultModal');
        if (existingModal) {
            existingModal.remove();
        }
        
        // Adiciona novo modal
        document.body.insertAdjacentHTML('beforeend', modal);
        
        // Mostra modal
        const modalElement = new bootstrap.Modal(document.getElementById('resultModal'));
        modalElement.show();
    }
    
    async downloadCsv() {
        try {
            const response = await fetch('/api/download_csv');
            
            if (response.ok) {
                const blob = await response.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `teste_agentgraph_${new Date().toISOString().slice(0, 19).replace(/:/g, '-')}.xlsx`;
                document.body.appendChild(a);
                a.click();
                window.URL.revokeObjectURL(url);
                document.body.removeChild(a);
                
                this.showAlert('Relatório baixado com sucesso!', 'success');
            } else {
                this.showAlert('Erro ao baixar relatório.', 'danger');
            }
        } catch (error) {
            this.showAlert('Erro ao baixar relatório: ' + error.message, 'danger');
        }
    }
    
    updateStatus(status) {
        const statusElement = document.getElementById('sessionStatus');
        statusElement.className = `status-badge status-${status}`;
        
        const statusText = {
            'idle': 'Aguardando',
            'running': 'Executando',
            'completed': 'Concluído',
            'error': 'Erro'
        };
        
        const statusIcon = {
            'idle': 'circle',
            'running': 'spinner fa-spin',
            'completed': 'check-circle',
            'error': 'exclamation-circle'
        };
        
        statusElement.innerHTML = `<i class="fas fa-${statusIcon[status]}"></i> ${statusText[status]}`;
    }
    
    showAlert(message, type) {
        // Remove alertas anteriores
        const existingAlerts = document.querySelectorAll('.alert-dismissible');
        existingAlerts.forEach(alert => alert.remove());
        
        const alert = document.createElement('div');
        alert.className = `alert alert-${type} alert-dismissible fade show`;
        alert.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        document.querySelector('.container-fluid').insertBefore(alert, document.querySelector('.row'));
        
        // Remove automaticamente após 5 segundos
        setTimeout(() => {
            if (alert.parentNode) {
                alert.remove();
            }
        }, 5000);
    }
}

// Inicializa o sistema
const testManager = new TestManager();

// Funções globais para os botões HTML
function cancelCurrentTest() {
    testManager.cancelCurrentTest();
}

function cancelAllTests() {
    testManager.cancelAllTests();
}

function skipStuckTests() {
    testManager.skipStuckTests();
}
