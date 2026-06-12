let allPanels = [];

        function renderPanelsTable(panels) {
            const tableBody = document.getElementById('panels-table-body');
            const countElement = document.getElementById('panels-count');

            if (!panels || panels.length === 0) {
                tableBody.innerHTML = '<tr><td colspan="5">No panels imported</td></tr>';
                countElement.textContent = '0 panels imported';
                return;
            }

            // Display panel count
            countElement.textContent = `${panels.length} panel(s) imported`;

            // Populate table rows
            tableBody.innerHTML = '';
            panels.forEach(panel => {
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td>${panel.sort_order}</td>
                    <td>${panel.panel_key}</td>
                    <td>${panel.panel_title}</td>
                    <td>${panel.html_id || ''}</td>
                    <td>
                        <select class="classification-select" data-panel-id="${panel.id}" onchange="updateClassification(this)">
                            <option value="unknown" ${panel.classification === 'unknown' ? 'selected' : ''}>unknown</option>
                            <option value="starter" ${panel.classification === 'starter' ? 'selected' : ''}>starter</option>
                            <option value="advanced" ${panel.classification === 'advanced' ? 'selected' : ''}>advanced</option>
                            <option value="project_specific" ${panel.classification === 'project_specific' ? 'selected' : ''}>project_specific</option>
                            <option value="debug" ${panel.classification === 'debug' ? 'selected' : ''}>debug</option>
                            <option value="skip" ${panel.classification === 'skip' ? 'selected' : ''}>skip</option>
                        </select>
                        <span class="status-text" id="status-${panel.id}" style="margin-left: 10px; font-size: 0.8em;"></span>
                    </td>
                `;
                tableBody.appendChild(row);
            });
        }

        function applyPanelFilters() {
            const searchInput = document.getElementById('panel-search');
            const classificationFilter = document.getElementById('panel-classification-filter');
            const sortField = document.getElementById('panel-sort-field');
            const sortDirection = document.getElementById('panel-sort-direction');

            const searchTerm = searchInput.value.toLowerCase();
            const selectedClassification = classificationFilter.value;

            // Filter panels
            let filteredPanels = allPanels.filter(panel => {
                // Search filter
                const matchesSearch =
                    panel.panel_key.toLowerCase().includes(searchTerm) ||
                    panel.panel_title.toLowerCase().includes(searchTerm) ||
                    (panel.html_id && panel.html_id.toLowerCase().includes(searchTerm));

                // Classification filter
                const matchesClassification = selectedClassification === '' || panel.classification === selectedClassification;

                return matchesSearch && matchesClassification;
            });

            // Sort panels
            const sortBy = sortField.value;
            const direction = sortDirection.value;

            filteredPanels.sort((a, b) => {
                let aValue = a[sortBy];
                let bValue = b[sortBy];

                // Handle null/undefined values
                if (aValue === null || aValue === undefined) aValue = '';
                if (bValue === null || bValue === undefined) bValue = '';

                // Convert to strings for comparison
                aValue = String(aValue);
                bValue = String(bValue);

                let comparison = 0;
                if (sortBy === 'classification') {
                    // For classification, we want to sort by the actual classification values
                    comparison = aValue.localeCompare(bValue);
                } else {
                    // For other fields, we want numeric sorting for sort_order
                    if (sortBy === 'sort_order' && !isNaN(aValue) && !isNaN(bValue)) {
                        comparison = Number(aValue) - Number(bValue);
                    } else {
                        comparison = aValue.localeCompare(bValue);
                    }
                }

                return direction === 'desc' ? -comparison : comparison;
            });

            renderPanelsTable(filteredPanels);
        }

        function initPanelFilters() {
            // Load saved filter values from localStorage if they exist
            const savedSearch = localStorage.getItem('dpmtf.panels.search');
            const savedClassification = localStorage.getItem('dpmtf.panels.classification');
            const savedSortField = localStorage.getItem('dpmtf.panels.sortField');
            const savedSortDirection = localStorage.getItem('dpmtf.panels.sortDirection');

            if (savedSearch) {
                document.getElementById('panel-search').value = savedSearch;
            }
            if (savedClassification) {
                document.getElementById('panel-classification-filter').value = savedClassification;
            }
            if (savedSortField) {
                document.getElementById('panel-sort-field').value = savedSortField;
            }
            if (savedSortDirection) {
                document.getElementById('panel-sort-direction').value = savedSortDirection;
            }

            // Attach event listeners
            document.getElementById('panel-search').addEventListener('input', function() {
                localStorage.setItem('dpmtf.panels.search', this.value);
                applyPanelFilters();
            });

            document.getElementById('panel-classification-filter').addEventListener('change', function() {
                localStorage.setItem('dpmtf.panels.classification', this.value);
                applyPanelFilters();
            });

            document.getElementById('panel-sort-field').addEventListener('change', function() {
                localStorage.setItem('dpmtf.panels.sortField', this.value);
                applyPanelFilters();
            });

            document.getElementById('panel-sort-direction').addEventListener('change', function() {
                localStorage.setItem('dpmtf.panels.sortDirection', this.value);
                applyPanelFilters();
            });

            // Initial filter application
            applyPanelFilters();
        }

        // Simple script to check database status
        fetch('/api/health')
            .then(response => response.json())
            .then(data => {
                const statusElement = document.getElementById('database-status');
                statusElement.textContent = data.database_exists ? 'Database found' : 'Database not found';
            })
            .catch(error => {
                console.error('Error checking database:', error);
                document.getElementById('database-status').textContent = 'Error checking database';
            });

        // Fetch and display panels
        function loadPanels() {
            const tableBody = document.getElementById('panels-table-body');
            const countElement = document.getElementById('panels-count');
            const errorElement = document.getElementById('panels-error');

            // Show loading message
            tableBody.innerHTML = '<tr><td colspan="5">Loading panels...</td></tr>';
            countElement.textContent = 'Loading panel data. ..';
            errorElement.style.display = 'none';

            fetch('/api/panels')
                .then(response => {
                    if (!response.ok) {
                        throw new Error('Network response was not ok');
                    }
                    return response.json();
                })
                .then(data => {
                    // Clear loading message
                    tableBody.innerHTML = '';
                    allPanels = data.panels || [];
                    applyPanelFilters();
                    return;

                    if (!data.panels || data.panels.length === 0) {
                        tableBody.innerHTML = '<tr><td colspan="5">No panels imported</td></tr>';
                        countElement.textContent = '0 panels imported';
                        return;
                    }

                    // Display panel count
                    countElement.textContent = `${data.panels.length} panel(s) imported`;

                    // Populate table rows
                    data.panels.forEach(panel => {
                        const row = document.createElement('tr');
                        row.innerHTML = `
                            <td>${panel.sort_order}</td>
                            <td>${panel.panel_key}</td>
                            <td>${panel.panel_title}</td>
                            <td>${panel.html_id || ''}</td>
                            <td>
                                <select class="classification-select" data-panel-id="${panel.id}" onchange="updateClassification(this)">
                                    <option value="unknown" ${panel.classification === 'unknown' ? 'selected' : ''}>unknown</option>
                                    <option value="starter" ${panel.classification === 'starter' ? 'selected' : ''}>starter</option>
                                    <option value="advanced" ${panel.classification === 'advanced' ? 'selected' : ''}>advanced</option>
                                    <option value="project_specific" ${panel.classification === 'project_specific' ? 'selected' : ''}>project_specific</option>
                                    <option value="debug" ${panel.classification === 'debug' ? 'selected' : ''}>debug</option>
                                    <option value="skip" ${panel.classification === 'skip' ? 'selected' : ''}>skip</option>
                                </select>
                                <span class="status-text" id="status-${panel.id}" style="margin-left: 10px; font-size: 0.8em;"></span>
                            </td>
                        `;
                        tableBody.appendChild(row);
                    });
                })
                .catch(error => {
                    console.error('Error fetching panels:', error);
                    errorElement.textContent = 'Error loading panels: ' + error.message;
                    errorElement.style.display = 'block';
                    tableBody.innerHTML = '<tr><td colspan="5">Failed to load panels</td></tr>';
                    countElement.textContent = 'Error loading panels';
                });
        }

        // Update classification for a panel
        function updateClassification(selectElement) {
            const panelId = parseInt(selectElement.dataset.panelId);
            const newClassification = selectElement.value;
            const statusElement = document.getElementById(`status-${panelId}`);

            // Show loading state
            statusElement.textContent = 'Saving. ..';
            statusElement.style.color = '#666';

            fetch(`/api/panels/${panelId}/classification`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    classification: newClassification
                })
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                return response.json();
            })
            .then(data => {
                statusElement.textContent = 'Saved';
                statusElement.style.color = 'green';
                // Clear status after 3 seconds
                setTimeout(() => {
                    statusElement.textContent = '';
                }, 3000);
            })
            .catch(error => {
                console.error('Error updating classification:', error);
                statusElement.textContent = 'Error';
                statusElement.style.color = 'red';
                // Clear status after 3 seconds
                setTimeout(() => {
                    statusElement.textContent = '';
                }, 3000);
            });
        }

        // Load app profiles
        function loadAppProfiles() {
            const selector = document.getElementById('profile-selector');
            const errorElement = document.getElementById('app-profiles-error');

            fetch('/api/app-profiles')
                .then(response => {
                    if (!response.ok) {
                        throw new Error('Network response was not ok');
                    }
                    return response.json();
                })
                .then(data => {
                    // Clear existing options
                    selector.innerHTML = '<option value="">Select a profile...</option>';

                    // Add profiles to selector with count information
                    data.profiles.forEach(profile => {
                        const option = document.createElement('option');
                        option.value = profile.id;
                        option.textContent = `${profile.name} (${profile.included_panel_count} panels)`;
                        selector.appendChild(option);
                    });
                })
                .catch(error => {
                    console.error('Error fetching app profiles:', error);
                    errorElement.textContent = 'Error loading app profiles: ' + error.message;
                    errorElement.style.display = 'block';
                });
        }

        // Create default profiles
        function createDefaultProfiles() {
            const btn = document.getElementById('create-default-profiles-btn');
            const errorElement = document.getElementById('app-profiles-error');

            btn.textContent = 'Creating. ..';
            btn.disabled = true;

            fetch('/api/app-profiles/defaults', {
                method: 'POST'
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                return response.json();
            })
            .then(data => {
                btn.textContent = 'Create Default Profiles';
                btn.disabled = false;
                loadAppProfiles();
                alert('Default profiles created successfully!');
            })
            .catch(error => {
                console.error('Error creating default profiles:', error);
                errorElement.textContent = 'Error creating default profiles: ' + error.message;
                errorElement.style.display = 'block';
                btn.textContent = 'Create Default Profiles';
                btn.disabled = false;
            });
        }

        // Load panels for a selected profile
        function loadProfilePanels() {
            const profileId = document.getElementById('profile-selector').value;
            const table = document.getElementById('profile-panels-table');
            const tableBody = document.getElementById('profile-panels-body');
            const errorElement = document.getElementById('app-profiles-error');

            if (!profileId) {
                table.style.display = 'none';
                return;
            }

            table.style.display = 'table';

            fetch(`/api/app-profiles/${profileId}/panels`)
                .then(response => {
                    if (!response.ok) {
                        throw new Error('Network response was not ok');
                    }
                    return response.json();
                })
                .then(data => {
                    tableBody.innerHTML = '';

                    if (!data.panels || data.panels.length === 0) {
                        tableBody.innerHTML = '<tr><td colspan="6">No panels in this profile</td></tr>';
                        return;
                    }

                    // Populate table rows
                    data.panels.forEach(panel => {
                        const row = document.createElement('tr');
                        row.innerHTML = `
                            <td>
                                <input type="checkbox" id="panel-${panel.id}" ${panel.included ? 'checked' : ''}
                                       onchange="updateProfilePanelMembership(${profileId}, ${panel.id}, this.checked)">
                            </td>
                            <td>${panel.id}</td>
                            <td>${panel.panel_key}</td>
                            <td>${panel.panel_title}</td>
                            <td>${panel.html_id || ''}</td>
                        `;
                        tableBody.appendChild(row);
                    });
                })
                .catch(error => {
                    console.error('Error fetching profile panels:', error);
                    errorElement.textContent = 'Error loading profile panels: ' + error.message;
                    errorElement.style.display = 'block';
                    table.style.display = 'none';
                });
        }

        // Update profile panel membership
        function updateProfilePanelMembership(profileId, panelId, included) {
            const errorElement = document.getElementById('app-profiles-error');

            fetch(`/api/app-profiles/${profileId}/panels/${panelId}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    include: included
                })
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                return response.json();
            })
            .then(data => {
                // Show success status
                console.log(`Panel ${panelId} ${included ? 'included' : 'excluded'} in profile ${profileId}`);
            })
            .catch(error => {
                console.error('Error updating profile panel membership:', error);
                errorElement.textContent = 'Error updating panel membership: ' + error.message;
                errorElement.style.display = 'block';
            });
        }

        // Load panels when page loads
        loadPanels();
        loadAppProfiles();
        loadPromptSequences();

        // Load prompt sequences when page loads
        function loadPromptSequences() {
            const selector = document.getElementById('sequence-selector');
            const errorElement = document.getElementById('prompt-sequence-error');

            fetch('/api/prompt-sequences')
                .then(response => {
                    if (!response.ok) {
                        throw new Error('Network response was not ok');
                    }
                    return response.json();
                })
                .then(data => {
                    // Clear existing options
                    selector.innerHTML = '<option value="">Select a sequence...</option>';

                    // Add sequences to selector
                    data.sequences.forEach(sequence => {
                        const option = document.createElement('option');
                        option.value = sequence.id;
                        option.textContent = `${sequence.name} (${sequence.status})`;
                        selector.appendChild(option);
                    });
                })
                .catch(error => {
                    console.error('Error fetching prompt sequences:', error);
                    errorElement.textContent = 'Error loading prompt sequences: ' + error.message;
                    errorElement.style.display = 'block';
                });
        }

        // Create a new prompt sequence
        function createPromptSequence() {
            const nameInput = document.getElementById('sequence-name');
            const goalInput = document.getElementById('sequence-goal');
            const btn = document.getElementById('create-sequence-btn');
            const errorElement = document.getElementById('prompt-sequence-error');

            const name = nameInput.value.trim();
            const goal = goalInput.value.trim();

            if (!name) {
                errorElement.textContent = 'Sequence name is required';
                errorElement.style.display = 'block';
                return;
            }

            btn.textContent = 'Creating. ..';
            btn.disabled = true;

            fetch('/api/prompt-sequences', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    name: name,
                    goal: goal
                })
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                return response.json();
            })
            .then(data => {
                btn.textContent = 'Create Sequence';
                btn.disabled = false;
                nameInput.value = '';
                goalInput.value = '';

                // Reload sequences to include the new one
                loadPromptSequences();

                // Update counts
                updateCounts();

                // Show success message
                alert('Sequence created successfully!');
            })
            .catch(error => {
                console.error('Error creating prompt sequence:', error);
                errorElement.textContent = 'Error creating prompt sequence: ' + error.message;
                errorElement.style.display = 'block';
                btn.textContent = 'Create Sequence';
                btn.disabled = false;
            });
        }

        // Load steps for a selected sequence
        function loadSequenceSteps() {
            const sequenceId = document.getElementById('sequence-selector').value;
            const container = document.getElementById('sequence-steps-container');
            const statusElement = document.getElementById('sequence-status');
            const errorElement = document.getElementById('prompt-sequence-error');

            if (!sequenceId) {
                // Show empty message if no sequence selected
                container.innerHTML = '<p id="empty-steps-message">No prompt sequences yet. Create the first sequence to begin planning small Claude Code prompts.</p>';
                statusElement.textContent = '';
                updateCounts(); // Update counts when no sequence is selected
                return;
            }

            // Show loading
            container.innerHTML = '<p>Loading steps...</p>';

            fetch(`/api/prompt-sequences/${sequenceId}/steps`)
                .then(response => {
                    if (!response.ok) {
                        throw new Error('Network response was not ok');
                    }
                    return response.json();
                })
                .then(data => {
                    // Get sequence info for status
                    fetch(`/api/prompt-sequences/${sequenceId}`)
                        .then(response => response.json())
                        .then(seqData => {
                            statusElement.textContent = `Status: ${seqData.sequences[0].status}`;
                        });

                    // Display steps
                    if (!data.steps || data.steps.length === 0) {
                        container.innerHTML = '<p>No steps in this sequence.</p>';
                        return;
                    }

                    let stepsHtml = '<table class="panel-table"><thead><tr><th>Step #</th><th>Title</th><th>Layer</th><th>Status</th><th>Result Note</th><th>Actions</th></tr></thead><tbody>';
                    data.steps.forEach(step => {
                        stepsHtml += `
                            <tr>
                                <td>${step.step_number}</td>
                                <td>${step.step_title}</td>
                                <td>${step.target_layer}</td>
                                <td>
                                    <select class="step-status-select" data-step-id="${step.id}" onchange="updateStepStatus(this)">
                                        <option value="planned" ${step.status === 'planned' ? 'selected' : ''}>planned</option>
                                        <option value="generated" ${step.status === 'generated' ? 'selected' : ''}>generated</option>
                                        <option value="implemented" ${step.status === 'implemented' ? 'selected' : ''}>implemented</option>
                                        <option value="failed" ${step.status === 'failed' ? 'selected' : ''}>failed</option>
                                        <option value="skipped" ${step.status === 'skipped' ? 'selected' : ''}>skipped</option>
                                    </select>
                                </td>
                                <td>
                                    <textarea class="step-result-note" data-step-id="${step.id}" rows="2" style="width: 100%;">${step.result_note || ''}</textarea>
                                </td>
                                <td>
                                    <button onclick="saveStepStatus(${step.id})">Save</button>
                                    <span class="step-status-message" id="status-${step.id}" style="margin-left: 10px; font-size: 0.8em;"></span>
                                </td>
                            </tr>
                        `;
                    });
                    stepsHtml += '</tbody></table>';
                    container.innerHTML = stepsHtml;

                    // Load prompt history after steps are displayed
                    loadPromptHistory();
                })
                .catch(error => {
                    console.error('Error fetching sequence steps:', error);
                    errorElement.textContent = 'Error loading sequence steps: ' + error.message;
                    errorElement.style.display = 'block';
                    container.innerHTML = '<p>Error loading steps.</p>';
                });
        }

        // Add a new step to the selected sequence
        function addPromptSequenceStep() {
            const sequenceId = document.getElementById('sequence-selector').value;
            const titleInput = document.getElementById('step-title');
            const layerSelect = document.getElementById('target-layer');
            const promptInput = document.getElementById('prompt-text');
            const btn = document.getElementById('add-step-btn');
            const errorElement = document.getElementById('prompt-sequence-error');

            if (!sequenceId) {
                errorElement.textContent = 'Please select a sequence first';
                errorElement.style.display = 'block';
                return;
            }

            const step_title = titleInput.value.trim();
            const target_layer = layerSelect.value;
            const prompt_text = promptInput.value.trim();

            if (!step_title) {
                errorElement.textContent = 'Step title is required';
                errorElement.style.display = 'block';
                return;
            }

            btn.textContent = 'Adding. ..';
            btn.disabled = true;

            fetch(`/api/prompt-sequences/${sequenceId}/steps`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    step_title: step_title,
                    target_layer: target_layer,
                    prompt_text: prompt_text
                })
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                return response.json();
            })
            .then(data => {
                btn.textContent = 'Add Step';
                btn.disabled = false;
                titleInput.value = '';
                promptInput.value = '';

                // Reload steps to include the new one
                loadSequenceSteps();

                // Update counts
                updateCounts();

                // Show success message
                alert('Step added successfully!');
            })
            .catch(error => {
                console.error('Error adding prompt sequence step:', error);
                errorElement.textContent = 'Error adding prompt sequence step: ' + error.message;
                errorElement.style.display = 'block';
                btn.textContent = 'Add Step';
                btn.disabled = false;
            });
        }

        // Generate next prompt preview
        function generateNextPrompt() {
            const sequenceId = document.getElementById('sequence-selector').value;
            const container = document.getElementById('prompt-preview-container');
            const messageElement = document.getElementById('prompt-preview-message');
            const previewElement = document.getElementById('prompt-preview');
            const copyBtn = document.getElementById('copy-prompt-btn');
            const btn = document.getElementById('generate-prompt-btn');
            const errorElement = document.getElementById('prompt-sequence-error');

            if (!sequenceId) {
                errorElement.textContent = 'Please select a sequence first';
                errorElement.style.display = 'block';
                return;
            }

            btn.textContent = 'Generating. ..';
            btn.disabled = true;
            messageElement.style.display = 'none';
            previewElement.style.display = 'none';
            copyBtn.style.display = 'none';

            fetch(`/api/prompt-sequences/${sequenceId}/next-prompt`)
            .then(response => response.json())
            .then(data => {
                btn.textContent = 'Generate Next Prompt Preview';
                btn.disabled = false;

                if (data.status === 'no_planned_steps') {
                    messageElement.textContent = 'No planned steps found in this sequence.';
                    messageElement.style.display = 'block';
                    return;
                }

                if (data.status === 'success') {
                    previewElement.value = data.generated_prompt;
                    previewElement.style.display = 'block';
                    copyBtn.style.display = 'inline-block';
                    messageElement.style.display = 'none';
                } else {
                    messageElement.textContent = 'Error generating prompt preview.';
                    messageElement.style.display = 'block';
                }
            })
            .catch(error => {
                console.error('Error generating next prompt:', error);
                btn.textContent = 'Generate Next Prompt Preview';
                btn.disabled = false;
                messageElement.textContent = 'Error generating prompt preview: ' + error.message;
                messageElement.style.display = 'block';
            });
        }

        // Copy prompt to clipboard
        function copyPrompt() {
            const previewElement = document.getElementById('prompt-preview');
            previewElement.select();
            document.execCommand('copy');
            alert('Prompt copied to clipboard!');
        }

        // Save generated prompt
        function saveGeneratedPrompt() {
            const sequenceId = document.getElementById('sequence-selector').value;
            const previewElement = document.getElementById('prompt-preview');
            const statusElement = document.getElementById('save-prompt-status');
            const saveSection = document.getElementById('save-prompt-section');

            if (!sequenceId) {
                alert('Please select a sequence first');
                return;
            }

            const generatedPrompt = previewElement.value;
            if (!generatedPrompt) {
                alert('No prompt to save');
                return;
            }

            // Show loading state
            statusElement.textContent = 'Saving. ..';
            statusElement.style.color = '#666';

            // Find the first planned step for this sequence to save against
            fetch(`/api/prompt-sequences/${sequenceId}/steps`)
            .then(response => response.json())
            .then(data => {
                const plannedStep = data.steps.find(step => step.status === 'planned');
                if (!plannedStep) {
                    statusElement.textContent = 'No planned step found to save against';
                    statusElement.style.color = 'red';
                    return;
                }

                // Save the generated prompt
                fetch(`/api/prompt-sequences/${sequenceId}/steps/${plannedStep.id}/generated-prompts`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        generated_prompt: generatedPrompt
                    })
                })
                .then(response => {
                    if (!response.ok) {
                        throw new Error('Network response was not ok');
                    }
                    return response.json();
                })
                .then(data => {
                    statusElement.textContent = 'Saved successfully';
                    statusElement.style.color = 'green';
                    // Clear status after 3 seconds
                    setTimeout(() => {
                        statusElement.textContent = '';
                    }, 3000);

                    // Reload prompt history to show the new entry
                    loadPromptHistory();
                })
                .catch(error => {
                    console.error('Error saving generated prompt:', error);
                    statusElement.textContent = 'Error saving prompt';
                    statusElement.style.color = 'red';
                    // Clear status after 3 seconds
                    setTimeout(() => {
                        statusElement.textContent = '';
                    }, 3000);
                });
            })
            .catch(error => {
                console.error('Error finding planned step:', error);
                statusElement.textContent = 'Error finding step';
                statusElement.style.color = 'red';
                // Clear status after 3 seconds
                setTimeout(() => {
                    statusElement.textContent = '';
                }, 3000);
            });
        }

        // Update step status
        function updateStepStatus(selectElement) {
            // This function just updates the UI state when a status is selected
            // The actual save happens when the Save button is clicked
        }

        // Save step status and result note
        function saveStepStatus(stepId, sequenceId) {
            // If sequenceId is not provided, get it from the selector
            if (!sequenceId) {
                const selector = document.getElementById('sequence-selector');
                sequenceId = selector.value;
            }

            const statusSelect = document.querySelector(`.step-status-select[data-step-id="${stepId}"]`);
            const noteTextarea = document.querySelector(`.step-result-note[data-step-id="${stepId}"]`);
            const statusElement = document.getElementById(`status-${stepId}`);

            const status = statusSelect.value;
            const resultNote = noteTextarea.value;

            // Show loading state
            statusElement.textContent = 'Saving. ..';
            statusElement.style.color = '#666';

            fetch(`/api/prompt-sequences/${sequenceId}/steps/${stepId}/status`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    status: status,
                    result_note: resultNote
                })
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                return response.json();
            })
            .then(data => {
                statusElement.textContent = 'Saved';
                statusElement.style.color = 'green';
                // Clear status after 3 seconds
                setTimeout(() => {
                    statusElement.textContent = '';
                }, 3000);
            })
            .catch(error => {
                console.error('Error updating step status:', error);
                statusElement.textContent = 'Error';
                statusElement.style.color = 'red';
                // Clear status after 3 seconds
                setTimeout(() => {
                    statusElement.textContent = '';
                }, 3000);
            });
        }

        // Load prompt history
        function loadPromptHistory() {
            const sequenceId = document.getElementById('sequence-selector').value;
            const container = document.getElementById('prompt-history-container');
            const messageElement = document.getElementById('prompt-history-message');
            const listElement = document.getElementById('prompt-history-list');

            if (!sequenceId) {
                messageElement.textContent = 'Select a sequence to view its prompt history.';
                messageElement.style.display = 'block';
                listElement.style.display = 'none';
                return;
            }

            // Show loading
            messageElement.textContent = 'Loading prompt history. ..';
            messageElement.style.display = 'block';
            listElement.style.display = 'none';

            fetch(`/api/prompt-sequences/${sequenceId}/generated-prompts`)
            .then(response => response.json())
            .then(data => {
                if (!data.generated_prompts || data.generated_prompts.length === 0) {
                    messageElement.textContent = 'No generated prompts found for this sequence.';
                    messageElement.style.display = 'block';
                    listElement.style.display = 'none';
                    return;
                }

                // Display history
                let historyHtml = '<div style="max-height: 400px; overflow-y: auto;">';
                data.generated_prompts.forEach(prompt => {
                    historyHtml += `
                        <div style="border: 1px solid #ddd; margin: 5px 0; padding: 10px; border-radius: 5px;">
                            <strong>Step ${prompt.step_number}: ${prompt.step_title}</strong> (${prompt.target_layer})
                            <br>
                            <small>Generated: ${prompt.generated_at}</small>
                            <br>
                            <pre style="background-color: #f5f5f5; padding: 8px; border-radius: 3px; font-size: 0.8em; white-space: pre-wrap; word-wrap: break-word;">${prompt.prompt_text}</pre>
                        </div>
                    `;
                });
                historyHtml += '</div>';

                listElement.innerHTML = historyHtml;
                messageElement.style.display = 'none';
                listElement.style.display = 'block';
            })
            .catch(error => {
                console.error('Error loading prompt history:', error);
                messageElement.textContent = 'Error loading prompt history: ' + error.message;
                messageElement.style.display = 'block';
                listElement.style.display = 'none';
            });
        }

        // Update sequence and step counts
        function updateCounts() {
            fetch('/api/prompt-sequences')
            .then(response => response.json())
            .then(data => {
                const sequenceCount = data.sequence_count || 0;
                const stepCount = data.total_step_count || 0;

                // Update UI elements
                document.getElementById('sequence-count').textContent = sequenceCount;
                document.getElementById('step-count').textContent = stepCount;
            })
            .catch(error => {
                console.error('Error updating counts:', error);
            });
        }

        // Load phase status
        function loadPhaseStatus() {
            fetch('/api/phase-status')
            .then(response => response.json())
            .then(data => {
                // Load completed phases
                const completedContainer = document.getElementById('completed-phases-container');
                if (data.completed && data.completed.length > 0) {
                    let completedHtml = '';
                    data.completed.forEach(phase => {
                        completedHtml += `
                            <div class="phase-card completed">
                                <h4>Phase ${phase.phase_key}</h4>
                                <p>${phase.phase_description}</p>
                            </div>
                        `;
                    });
                    completedContainer.innerHTML = completedHtml;
                } else {
                    completedContainer.innerHTML = '<p>No completed phases found.</p>';
                }

                // Load next phases
                const nextContainer = document.getElementById('next-phases-container');
                if (data.next && data.next.length > 0) {
                    let nextHtml = '';
                    data.next.forEach(phase => {
                        nextHtml += `
                            <div class="phase-card">
                                <h4>Phase ${phase.phase_key}</h4>
                                <p>${phase.phase_description}</p>
                            </div>
                        `;
                    });
                    nextContainer.innerHTML = nextHtml;
                } else {
                    nextContainer.innerHTML = '<p>No next phases found.</p>';
                }
            })
            .catch(error => {
                console.error('Error loading phase status:', error);
                // Show fallback message
                document.getElementById('completed-phases-container').innerHTML =
                    '<p>Error loading phase status. Please refresh the page.</p>';
                document.getElementById('next-phases-container').innerHTML =
                    '<p>Error loading phase status. Please refresh the page.</p>';
            });
        }

        // Load phase status with filtering
        function loadPhaseStatusWithFilter() {
            // Check if we should show completed phases
            const showCompleted = localStorage.getItem('dpmtf.phaseStatus.showCompleted') === 'true';

            // Load the phase status data
            fetch('/api/phase-status')
            .then(response => response.json())
            .then(data => {
                // Load completed phases
                const completedContainer = document.getElementById('completed-phases-container');
                if (data.completed && data.completed.length > 0) {
                    let completedHtml = '';
                    if (showCompleted) {
                        data.completed.forEach(phase => {
                            completedHtml += `
                                <div class="phase-card completed">
                                    <h4>Phase ${phase.phase_key}</h4>
                                    <p>${phase.phase_description}</p>
                                </div>
                            `;
                        });
                    }
                    completedContainer.innerHTML = completedHtml || '<p>No completed phases found.</p>';
                } else {
                    completedContainer.innerHTML = '<p>No completed phases found.</p>';
                }

                // Load next phases
                const nextContainer = document.getElementById('next-phases-container');
                if (data.next && data.next.length > 0) {
                    let nextHtml = '';
                    data.next.forEach(phase => {
                        nextHtml += `
                            <div class="phase-card">
                                <h4>Phase ${phase.phase_key}</h4>
                                <p>${phase.phase_description}</p>
                            </div>
                        `;
                    });
                    nextContainer.innerHTML = nextHtml;
                } else {
                    nextContainer.innerHTML = '<p>No next phases found.</p>';
                }

                // Load planned phases
                const plannedContainer = document.getElementById('planned-phases-container');
                if (data.planned && data.planned.length > 0) {
                    let plannedHtml = '';
                    data.planned.forEach(phase => {
                        plannedHtml += `
                            <div class="phase-card">
                                <h4>Phase ${phase.phase_key}</h4>
                                <p>${phase.phase_description}</p>
                            </div>
                        `;
                    });
                    plannedContainer.innerHTML = plannedHtml;
                } else {
                    plannedContainer.innerHTML = '<p>No planned phases found.</p>';
                }
            })
            .catch(error => {
                console.error('Error loading phase status:', error);
                // Show fallback message
                document.getElementById('completed-phases-container').innerHTML =
                    '<p>Error loading phase status. Please refresh the page.</p>';
                document.getElementById('next-phases-container').innerHTML =
                    '<p>Error loading phase status. Please refresh the page.</p>';
                document.getElementById('planned-phases-container').innerHTML =
                    '<p>Error loading phase status. Please refresh the page.</p>';
            });
        }

        // Toggle completed phases visibility
        function toggleCompletedPhases() {
            const checkbox = document.getElementById('show-completed-phases');
            const showCompleted = checkbox.checked;

            // Save to localStorage
            localStorage.setItem('dpmtf.phaseStatus.showCompleted', showCompleted);

            // Reload phase status with new setting
            loadPhaseStatusWithFilter();
        }

        // Initialize phase status filters
        function initPhaseStatusFilters() {
            // Add the toggle checkbox outside the completed phases section to prevent overwriting
            const completedContainer = document.getElementById('completed-phases-container');
            const parentContainer = completedContainer.parentElement;

            // Create toggle container
            const toggleContainer = document.createElement('div');
            toggleContainer.style.marginBottom = '10px';
            toggleContainer.innerHTML = `
                <input type="checkbox" id="show-completed-phases" style="margin-right: 5px;">
                <label for="show-completed-phases">Show completed phases</label>
            `;

            // Insert toggle before completed container
            parentContainer.insertBefore(toggleContainer, completedContainer);

            // Set initial state from localStorage
            const showCompleted = localStorage.getItem('dpmtf.phaseStatus.showCompleted') === 'true';
            document.getElementById('show-completed-phases').checked = showCompleted;

            // Add event listener
            document.getElementById('show-completed-phases').addEventListener('change', toggleCompletedPhases);

            // Load phase status with initial filter state
            loadPhaseStatusWithFilter();
        }

        // Create draft prompt sequence
        function createDraftPromptSequence() {
            const profileId = document.getElementById('profile-selector').value;
            const statusElement = document.getElementById('draft-sequence-status');
            const btn = document.getElementById('create-draft-sequence-btn');

            if (!profileId) {
                alert('Please select an app profile first');
                return;
            }

            // Show loading state
            btn.textContent = 'Creating. ..';
            btn.disabled = true;
            statusElement.textContent = 'Creating draft sequence. ..';
            statusElement.style.color = '#666';

            fetch(`/api/app-profiles/${profileId}/draft-prompt-sequence`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                }
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                return response.json();
            })
            .then(data => {
                btn.textContent = 'Create Draft Prompt Sequence';
                btn.disabled = false;
                statusElement.textContent = `Created sequence ${data.sequence_id} with ${data.created_steps_count} steps`;
                statusElement.style.color = 'green';

                // Clear status after 5 seconds
                setTimeout(() => {
                    statusElement.textContent = '';
                }, 5000);

                // Refresh prompt sequences to show the new sequence
                loadPromptSequences();
            })
            .catch(error => {
                console.error('Error creating draft prompt sequence:', error);
                btn.textContent = 'Create Draft Prompt Sequence';
                btn.disabled = false;
                statusElement.textContent = 'Error creating draft sequence';
                statusElement.style.color = 'red';

                // Clear status after 5 seconds
                setTimeout(() => {
                    statusElement.textContent = '';
                }, 5000);
            });
        }

        // Load project plans
        function loadProjectPlans() {
            const container = document.getElementById('project-plans-container');

            // Show loading message
            if (container) {
                container.innerHTML = '<p>Loading project plans...</p>';
            }

            fetch('/api/project-plans')
            .then(response => response.json())
            .then(data => {
                if (!container) {
                    console.error('project-plans-container not found');
                    return;
                }

                if (!data.project_plans || data.project_plans.length === 0) {
                    container.innerHTML = '<p>No project plans created yet.</p>';
                    return;
                }

                let plansHtml = '<table class="panel-table"><thead><tr><th>Name</th><th>Folder</th><th>Port</th><th>Profile</th><th>Sequence</th><th>Status</th><th>Created</th></tr></thead><tbody>';
                data.project_plans.forEach(plan => {
                    plansHtml += `
                        <tr>
                            <td>${plan.project_name}</td>
                            <td>${plan.target_folder}</td>
                            <td>${plan.app_port || ''}</td>
                            <td>${plan.app_profile_name || ''}</td>
                            <td>${plan.prompt_sequence_name || ''}</td>
                            <td>${plan.status}</td>
                            <td>${plan.created_at}</td>
                        </tr>
                    `;
                });
                plansHtml += '</tbody></table>';
                container.innerHTML = plansHtml;
            })
            .catch(error => {
                console.error('Error loading project plans:', error);
                if (container) {
                    container.innerHTML = '<p>Error loading project plans.</p>';
                }
            });
        }

        // Create project plan
        function createProjectPlan() {
            const projectName = document.getElementById('project-name').value;
            const targetFolder = document.getElementById('target-folder').value;
            const appPort = document.getElementById('app-port').value;
            const appProfileId = document.getElementById('app-profile').value;
            const promptSequenceId = document.getElementById('prompt-sequence').value;
            const notes = document.getElementById('notes').value;
            const statusElement = document.getElementById('project-plan-status');
            const errorElement = document.getElementById('project-plan-error');
            const btn = document.getElementById('create-project-plan-btn');

            // Validate inputs
            if (!projectName.trim()) {
                errorElement.textContent = 'Project name is required';
                errorElement.style.display = 'block';
                return;
            }

            if (!targetFolder.trim()) {
                errorElement.textContent = 'Target folder is required';
                errorElement.style.display = 'block';
                return;
            }

            // Show loading state
            btn.textContent = 'Creating. ..';
            btn.disabled = true;
            errorElement.style.display = 'none';
            statusElement.textContent = 'Creating project plan. ..';
            statusElement.style.color = '#666';

            // Prepare data
            const projectData = {
                project_name: projectName,
                target_folder: targetFolder,
                notes: notes
            };

            if (appPort) projectData.app_port = parseInt(appPort);
            if (appProfileId) projectData.app_profile_id = parseInt(appProfileId);
            if (promptSequenceId) projectData.prompt_sequence_id = parseInt(promptSequenceId);

            fetch('/api/project-plans', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(projectData)
            })
            .then(response => response.json())
            .then(data => {
                btn.textContent = 'Create Project Plan';
                btn.disabled = false;
                statusElement.textContent = 'Project plan created successfully';
                statusElement.style.color = 'green';

                // Clear form
                document.getElementById('project-name').value = '';
                document.getElementById('target-folder').value = '';
                document.getElementById('app-port').value = '';
                document.getElementById('app-profile').value = '';
                document.getElementById('prompt-sequence').value = '';
                document.getElementById('notes').value = '';

                // Reload project plans
                loadProjectPlans();

                // Clear status after 3 seconds
                setTimeout(() => {
                    statusElement.textContent = '';
                }, 3000);
            })
            .catch(error => {
                console.error('Error creating project plan:', error);
                btn.textContent = 'Create Project Plan';
                btn.disabled = false;
                errorElement.textContent = 'Error creating project plan: ' + error.message;
                errorElement.style.display = 'block';
            });
        }

        // Load dropdown data for project planning
        function loadProjectPlanningDropdowns() {
            // Load app profiles
            fetch('/api/app-profiles')
            .then(response => response.json())
            .then(data => {
                const profileSelect = document.getElementById('app-profile');
                if (!profileSelect) {
                    console.error('app-profile dropdown not found');
                    return;
                }

                // Clear existing options except the placeholder
                while (profileSelect.options.length > 0) {
                    profileSelect.remove(0);
                }

                // Add placeholder option
                const placeholderOption = document.createElement('option');
                placeholderOption.value = '';
                placeholderOption.textContent = 'Select an app profile';
                profileSelect.appendChild(placeholderOption);

                if (data.profiles && data.profiles.length > 0) {
                    data.profiles.forEach(profile => {
                        const option = document.createElement('option');
                        option.value = profile.id;
                        option.textContent = profile.name;
                        profileSelect.appendChild(option);
                    });
                }
            })
            .catch(error => {
                console.error('Error loading app profiles:', error);
                const profileSelect = document.getElementById('app-profile');
                if (profileSelect) {
                    // Clear existing options except the placeholder
                    while (profileSelect.options.length > 0) {
                        profileSelect.remove(0);
                    }
                    // Add placeholder option
                    const placeholderOption = document.createElement('option');
                    placeholderOption.value = '';
                    placeholderOption.textContent = 'Select an app profile';
                    profileSelect.appendChild(placeholderOption);
                }
            });

            // Load prompt sequences
            fetch('/api/prompt-sequences')
            .then(response => response.json())
            .then(data => {
                const sequenceSelect = document.getElementById('prompt-sequence');
                if (!sequenceSelect) {
                    console.error('prompt-sequence dropdown not found');
                    return;
                }

                // Clear existing options except the placeholder
                while (sequenceSelect.options.length > 0) {
                    sequenceSelect.remove(0);
                }

                // Add placeholder option
                const placeholderOption = document.createElement('option');
                placeholderOption.value = '';
                placeholderOption.textContent = 'Select a prompt sequence';
                sequenceSelect.appendChild(placeholderOption);

                if (data.sequences && data.sequences.length > 0) {
                    data.sequences.forEach(sequence => {
                        const option = document.createElement('option');
                        option.value = sequence.id;
                        option.textContent = sequence.name;
                        sequenceSelect.appendChild(option);
                    });
                }
            })
            .catch(error => {
                console.error('Error loading prompt sequences:', error);
                const sequenceSelect = document.getElementById('prompt-sequence');
                if (sequenceSelect) {
                    // Clear existing options except the placeholder
                    while (sequenceSelect.options.length > 0) {
                        sequenceSelect.remove(0);
                    }
                    // Add placeholder option
                    const placeholderOption = document.createElement('option');
                    placeholderOption.value = '';
                    placeholderOption.textContent = 'Select a prompt sequence';
                    sequenceSelect.appendChild(placeholderOption);
                }
            });
        }

        // Load database layout preview
        function loadDatabaseLayoutPreview() {
            const container = document.getElementById('database-layout-preview-container');
            const statusElement = document.getElementById('database-layout-preview-status');

            // Clear previous content
            container.replaceChildren();
            statusElement.textContent = '';

            // Show loading message
            const loadingElement = document.createElement('p');
            loadingElement.textContent = 'Loading database layout preview...';
            container.appendChild(loadingElement);

            fetch('/api/frontend-layout')
                .then(response => {
                    if (!response.ok) {
                        throw new Error('Network response was not ok');
                    }
                    return response.json();
                })
                .then(data => {
                    // Remove loading message
                    container.removeChild(loadingElement);

                    // Check if we have layout data
                    if (!data.layout_slots || !data.layout_panels) {
                        const errorElement = document.createElement('p');
                        errorElement.textContent = 'No layout data available';
                        errorElement.className = 'error-message';
                        container.appendChild(errorElement);
                        return;
                    }

                    // Sort slots by display_order
                    const sortedSlots = [...data.layout_slots].sort((a, b) => a.display_order - b.display_order);

                    // Group panels by slot_id
                    const panelsBySlot = {};
                    data.layout_panels.forEach(panel => {
                        if (!panelsBySlot[panel.slot_id]) {
                            panelsBySlot[panel.slot_id] = [];
                        }
                        panelsBySlot[panel.slot_id].push(panel);
                    });

                    // Render each slot
                    sortedSlots.forEach(slot => {
                        const slotElement = document.createElement('div');
                        slotElement.className = 'layout-slot';

                        // Slot header
                        const slotHeader = document.createElement('h5');
                        slotHeader.textContent = `${slot.slot_name} (${slot.slot_id})`;
                        slotElement.appendChild(slotHeader);

                        // Slot description
                        const slotDescription = document.createElement('p');
                        slotDescription.textContent = slot.slot_description;
                        slotDescription.className = 'layout-muted';
                        slotElement.appendChild(slotDescription);

                        // Panel count
                        const panelCount = panelsBySlot[slot.slot_id] ? panelsBySlot[slot.slot_id].length : 0;
                        const panelCountElement = document.createElement('p');
                        panelCountElement.textContent = `${panelCount} panel(s)`;
                        panelCountElement.className = 'layout-muted';
                        slotElement.appendChild(panelCountElement);

                        // Panel list
                        if (panelsBySlot[slot.slot_id] && panelsBySlot[slot.slot_id].length > 0) {
                            const panelsContainer = document.createElement('div');
                            panelsContainer.className = 'slot-panels';

                            // Sort panels by display_order
                            const sortedPanels = [...panelsBySlot[slot.slot_id]].sort((a, b) => a.display_order - b.display_order);

                            sortedPanels.forEach(panel => {
                                const panelLine = document.createElement('div');
                                panelLine.className = 'panel-line';
                                panelLine.textContent = `${panel.panel_id} · ${panel.panel_key} · ${panel.panel_type}`;
                                panelsContainer.appendChild(panelLine);
                            });

                            slotElement.appendChild(panelsContainer);
                        }

                        container.appendChild(slotElement);
                    });
                })
                .catch(error => {
                    console.error('Error loading database layout preview:', error);
                    container.removeChild(loadingElement);
                    const errorElement = document.createElement('p');
                    errorElement.textContent = 'Error loading database layout preview: ' + error.message;
                    errorElement.className = 'error-message';
                    container.appendChild(errorElement);
                });
        }

        // Load i18n label preview
        function loadI18nLabelPreview() {
            const container = document.getElementById('i18n-label-preview-container');
            const statusElement = document.getElementById('i18n-label-preview-status');
            const localeSelect = document.getElementById('i18n-preview-locale');

            // Clear previous content
            container.replaceChildren();
            if (statusElement) {
                statusElement.textContent = '';
            }

            const locale = localeSelect ? localeSelect.value : 'en-US';

            // Show loading message
            const loadingElement = document.createElement('p');
            loadingElement.textContent = 'Loading i18n labels...';
            container.appendChild(loadingElement);

            fetch('/api/ui-labels/system_setup?locale=' + encodeURIComponent(locale))
                .then(response => {
                    if (!response.ok) {
                        throw new Error('Network response was not ok');
                    }
                    return response.json();
                })
                .then(data => {
                    // Remove loading message
                    container.removeChild(loadingElement);

                    // Check if we have labels data
                    if (!data.labels || typeof data.labels !== 'object') {
                        const errorElement = document.createElement('p');
                        errorElement.textContent = 'No label data available';
                        errorElement.className = 'error-message';
                        container.appendChild(errorElement);
                        return;
                    }

                    // Render each label as a compact row
                    Object.keys(data.labels).forEach(function(labelKey) {
                        const resolvedText = data.labels[labelKey];

                        const rowElement = document.createElement('div');
                        rowElement.className = 'i18n-label-row';

                        const keySpan = document.createElement('span');
                        keySpan.className = 'i18n-label-key';
                        keySpan.textContent = labelKey;
                        rowElement.appendChild(keySpan);

                        const textSpan = document.createElement('span');
                        textSpan.className = 'i18n-label-text';
                        textSpan.textContent = resolvedText;
                        rowElement.appendChild(textSpan);

                        container.appendChild(rowElement);
                    });

                    if (statusElement) {
                        statusElement.textContent = 'Resolved for locale: ' + data.locale + ' (' + Object.keys(data.labels).length + ' labels)';
                    }
                })
                .catch(error => {
                    console.error('Error loading i18n label preview:', error);
                    container.removeChild(loadingElement);
                    const errorElement = document.createElement('p');
                    errorElement.textContent = 'Error loading i18n labels: ' + error.message;
                    errorElement.className = 'error-message';
                    container.appendChild(errorElement);
                });
        }

        // Load endpoint registry preview
        function loadEndpointRegistryPreview() {
            const container = document.getElementById('endpoint-registry-preview-container');
            const statusElement = document.getElementById('endpoint-registry-preview-status');

            // Clear previous content
            container.replaceChildren();
            if (statusElement) {
                statusElement.textContent = '';
            }

            // Show loading message
            const loadingElement = document.createElement('p');
            loadingElement.textContent = 'Loading endpoint registry...';
            container.appendChild(loadingElement);

            fetch('/api/endpoint-registry')
                .then(response => {
                    if (!response.ok) {
                        throw new Error('Network response was not ok');
                    }
                    return response.json();
                })
                .then(data => {
                    // Remove loading message
                    container.removeChild(loadingElement);

                    // Check if we have endpoint data
                    if (!data.endpoint_registry || !Array.isArray(data.endpoint_registry)) {
                        const errorElement = document.createElement('p');
                        errorElement.textContent = 'No endpoint registry data available';
                        errorElement.className = 'error-message';
                        container.appendChild(errorElement);
                        return;
                    }

                    // Render each endpoint as a compact row
                    data.endpoint_registry.forEach(function(endpoint) {
                        const rowElement = document.createElement('div');
                        rowElement.className = 'endpoint-row';

                        // Primary info: method, route path, endpoint key
                        const routeSpan = document.createElement('span');
                        routeSpan.className = 'endpoint-route';
                        routeSpan.textContent = endpoint.http_method + ' ' + endpoint.route_path;
                        rowElement.appendChild(routeSpan);

                        // Meta info: endpoint_id, frontend_consumer, response_shape
                        const metaSpan = document.createElement('span');
                        metaSpan.className = 'endpoint-meta';
                        var metaParts = [endpoint.endpoint_id, endpoint.endpoint_key];
                        if (endpoint.frontend_consumer) {
                            metaParts.push(endpoint.frontend_consumer);
                        }
                        if (endpoint.response_shape) {
                            metaParts.push(endpoint.response_shape);
                        }
                        metaSpan.textContent = metaParts.join(' · ');
                        rowElement.appendChild(metaSpan);

                        container.appendChild(rowElement);
                    });

                    if (statusElement) {
                        statusElement.textContent = data.endpoint_registry.length + ' endpoint(s) loaded';
                    }
                })
                .catch(error => {
                    console.error('Error loading endpoint registry preview:', error);
                    container.removeChild(loadingElement);
                    const errorElement = document.createElement('p');
                    errorElement.textContent = 'Error loading endpoint registry: ' + error.message;
                    errorElement.className = 'error-message';
                    container.appendChild(errorElement);
                });
        }

        // System Setup Drawer Functions
        function initSystemSetupDrawer() {
            const drawer = document.getElementById('system-setup-drawer');
            const openButton = document.getElementById('system-setup-btn');
            const closeButton = document.getElementById('system-setup-close-btn');
            const refreshButton = document.getElementById('refresh-layout-preview-btn');
            const refreshI18nButton = document.getElementById('refresh-i18n-preview-btn');
            const localeSelect = document.getElementById('i18n-preview-locale');
            const refreshEndpointRegistryButton = document.getElementById('refresh-endpoint-registry-btn');

            if (drawer) {
                drawer.classList.remove('open');
            }

            if (openButton) {
                openButton.addEventListener('click', openSystemSetupDrawer);
            }

            if (closeButton) {
                closeButton.addEventListener('click', closeSystemSetupDrawer);
            }

            if (refreshButton) {
                refreshButton.addEventListener('click', loadDatabaseLayoutPreview);
            }

            if (refreshI18nButton) {
                refreshI18nButton.addEventListener('click', loadI18nLabelPreview);
            }

            if (localeSelect) {
                localeSelect.addEventListener('change', loadI18nLabelPreview);
            }

            if (refreshEndpointRegistryButton) {
                refreshEndpointRegistryButton.addEventListener('click', loadEndpointRegistryPreview);
            }
        }

        function openSystemSetupDrawer() {
            document.getElementById('system-setup-drawer').classList.add('open');
            // Load layout preview when drawer opens
            loadDatabaseLayoutPreview();
            // Load i18n label preview when drawer opens
            loadI18nLabelPreview();
            // Load endpoint registry preview when drawer opens
            loadEndpointRegistryPreview();
        }

        function closeSystemSetupDrawer() {
            document.getElementById('system-setup-drawer').classList.remove('open');
        }

        // ── Phase 2F: Hitrate Scoring ──────────────────────────────

        function loadHitrates() {
            var statusEl = document.getElementById("hitrate-status");
            var table = document.getElementById("hitrate-table");
            var tbody = document.getElementById("hitrate-table-body");
            var loadingEl = document.getElementById("hitrate-loading");

            statusEl.textContent = "";
            loadingEl.style.display = "block";
            table.style.display = "none";

            fetch("/api/prompt-hirates")
                .then(function (res) {
                    if (!res.ok) throw new Error("HTTP " + res.status);
                    return res.json();
                })
                .then(function (data) {
                    loadingEl.style.display = "none";
                    var hitrates = data.hitrates || [];

                    if (!hitrates.length) {
                        tbody.replaceChildren();
                        var row = document.createElement("tr");
                        var cell = document.createElement("td");
                        cell.colSpan = 4;
                        cell.textContent = "No hitrate data yet. Run a prompt phase to populate.";
                        row.appendChild(cell);
                        tbody.appendChild(row);
                        table.style.display = "table";
                        statusEl.textContent = "0 phases tracked";
                        return;
                    }

                    tbody.replaceChildren();
                    hitrates.forEach(function (h) {
                        var row = document.createElement("tr");
                        var pct = (h.rolling_success_rate * 100).toFixed(0);

                        // Color-code the success rate
                        var rateClass = pct >= 80 ? "hitrate-good" :
                                        pct >= 50 ? "hitrate-ok" : "hitrate-low";

                        row.appendChild(td(h.phase_key));
                        row.appendChild(td(pct + "%", rateClass));
                        row.appendChild(td(h.successful_runs + " / " + h.total_runs));
                        row.appendChild(td(h.last_run_timestamp ?
                            new Date(h.last_run_timestamp).toLocaleString() : "-"));
                        tbody.appendChild(row);
                    });

                    table.style.display = "table";
                    statusEl.textContent = hitrates.length + " phase(s) tracked";
                })
                .catch(function (err) {
                    loadingEl.style.display = "none";
                    statusEl.textContent = "Error: " + err.message;
                });
        }

        function loadPromptRuns() {
            var tbody = document.getElementById("prompt-runs-table-body");
            var table = document.getElementById("prompt-runs-table");
            var loadingEl = document.getElementById("prompt-runs-loading");

            loadingEl.style.display = "block";
            table.style.display = "none";

            fetch("/api/prompt-runs?limit=20")
                .then(function (res) {
                    if (!res.ok) throw new Error("HTTP " + res.status);
                    return res.json();
                })
                .then(function (data) {
                    loadingEl.style.display = "none";
                    var runs = data.runs || [];

                    if (!runs.length) {
                        tbody.replaceChildren();
                        var row = document.createElement("tr");
                        var cell = document.createElement("td");
                        cell.colSpan = 7;
                        cell.textContent = "No prompt runs recorded yet.";
                        row.appendChild(cell);
                        tbody.appendChild(row);
                        table.style.display = "table";
                        return;
                    }

                    tbody.replaceChildren();
                    runs.forEach(function (r) {
                        var row = document.createElement("tr");
                        row.appendChild(td(r.run_id));
                        row.appendChild(td(r.phase_key));
                        row.appendChild(td(r.target_project));
                        row.appendChild(td(r.success ? "✓" : "✗",
                            r.success ? "hitrate-good" : "hitrate-low"));
                        row.appendChild(td(r.duration_seconds != null ?
                            r.duration_seconds + "s" : "-"));
                        row.appendChild(td(r.model_used || "-"));
                        row.appendChild(td(r.run_timestamp ?
                            new Date(r.run_timestamp).toLocaleString() : "-"));
                        tbody.appendChild(row);
                    });

                    table.style.display = "table";
                })
                .catch(function (err) {
                    loadingEl.style.display = "none";
                });
        }

        function td(text, className) {
            var cell = document.createElement("td");
            cell.textContent = text;
            if (className) cell.className = className;
            return cell;
        }

        // Initialize hitrate display
        loadHitrates();
        loadPromptRuns();

        // Initialize system setup drawer before other startup calls
        initSystemSetupDrawer();

        // Load initial data
        loadPanels();
        loadAppProfiles();
        loadPromptSequences();
        updateCounts();
        loadPhaseStatusWithFilter();
        initPanelFilters();
        initPhaseStatusFilters();
        loadProjectPlans();
        loadProjectPlanningDropdowns();

