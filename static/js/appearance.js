(() => {
    const shell = document.querySelector('.workspace-shell');
    if (!shell) return;

    const process = shell.dataset.process;
    const scanForm = document.getElementById('scan-form');
    const input = document.getElementById('employee-id-input');
    const message = document.getElementById('message');
    const employeeCard = document.getElementById('employee-card');
    const saveCheck = document.getElementById('save-check');
    const comment = document.getElementById('check-comment');
    let currentEmployee = null;
    let selectedStatus = null;

    const csrfToken = () => {
        const name = 'csrftoken=';
        const cookie = document.cookie.split(';').map(v => v.trim()).find(v => v.startsWith(name));
        return cookie ? decodeURIComponent(cookie.substring(name.length)) : '';
    };

    const postJson = async (url, payload) => {
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken(),
            },
            body: JSON.stringify(payload),
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || 'Request failed.');
        return data;
    };

    const showMessage = (text, type = 'info') => {
        message.textContent = text;
        message.className = `alert alert-${type}`;
    };

    const initials = (name) => name.split(/\s+/).filter(Boolean).slice(0, 2).map(v => v[0]).join('').toUpperCase();
    const firstInitial = (name) => String(name || '?').trim().charAt(0).toUpperCase() || '?';
    const escapeHtml = (value) => String(value ?? '').replace(/[&<>'"]/g, (char) => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]));
    const statusClass = (value) => String(value || '').toLowerCase().replaceAll(' ', '_');
    const shiftClass = (value) => String(value || '').toLowerCase().replaceAll(' ', '_');

    const renderTattoos = (tattoos) => {
        const summary = document.getElementById('tattoo-summary');
        const records = document.getElementById('tattoo-records');
        records.innerHTML = '';

        if (!tattoos?.has_record) {
            summary.className = 'tattoo-summary unknown';
            summary.textContent = 'No active tattoo record was found for this Employee ID.';
            return;
        }

        if (tattoos.cover_required) {
            summary.className = 'tattoo-summary cover';
            summary.textContent = 'Tattoo record found — coverage is required.';
        } else {
            summary.className = 'tattoo-summary clear';
            summary.textContent = 'Tattoo record found — coverage is not required.';
        }

        tattoos.records.forEach((item) => {
            const el = document.createElement('div');
            el.className = 'tattoo-item';
            const cover = item.should_be_covered === true ? 'Yes' : item.should_be_covered === false ? 'No' : 'Not specified';
            el.innerHTML = `<strong>Cover required: ${cover}</strong><p>${escapeHtml(item.details || 'Tattoo record')}</p><p>Location: ${escapeHtml(item.location || 'Not specified')}</p>${item.connotation ? `<p>Connotation: ${escapeHtml(item.connotation)}</p>` : ''}`;
            records.appendChild(el);
        });
    };

    const renderApprovals = (approvals) => {
        const summary = document.getElementById('approval-summary');
        const records = document.getElementById('approval-records');
        records.innerHTML = '';

        if (!approvals?.has_record) {
            summary.className = 'approval-summary unknown';
            summary.textContent = 'No active appearance approval record was found for this Employee ID.';
            return;
        }

        const hasRejected = approvals.records.some(item => item.status === 'REJECTED');
        const hasInProgress = approvals.records.some(item => item.status === 'IN_PROGRESS');

        if (hasRejected) {
            summary.className = 'approval-summary rejected';
            summary.textContent = 'Appearance approval record found — review required.';
        } else if (hasInProgress) {
            summary.className = 'approval-summary pending';
            summary.textContent = 'Appearance approval record found — approval is in progress.';
        } else {
            summary.className = 'approval-summary approved';
            summary.textContent = 'Appearance approval record found.';
        }

        approvals.records.forEach((item) => {
            const el = document.createElement('div');
            el.className = 'approval-item';
            const details = [
                item.responsible ? `<p>Responsible: ${escapeHtml(item.responsible)}</p>` : '',
                `<p>Medical condition: ${escapeHtml(item.medical_condition || 'Not specified')}</p>`,
                `<p>Test time frame needed: ${escapeHtml(item.test_time_frame_needed || 'Not specified')}</p>`,
                `<p>Paperwork submitted: ${escapeHtml(item.paperwork_submitted || 'Not specified')}</p>`,
                item.test_initial_date ? `<p>Initial date: ${escapeHtml(item.test_initial_date)}</p>` : '',
                item.test_final_date ? `<p>Final date: ${escapeHtml(item.test_final_date)}</p>` : '',
                item.comments ? `<p>Comments: ${escapeHtml(item.comments)}</p>` : '',
            ].join('');

            el.innerHTML = `<div class="approval-item-head"><strong>${escapeHtml(item.situation || 'Appearance approval')}</strong><span class="approval-status approval-status-${escapeHtml((item.status || 'UNKNOWN').toLowerCase())}">${escapeHtml(item.status_label || 'Not specified')}</span></div>${details}`;
            records.appendChild(el);
        });
    };

    const renderEmployee = (employee) => {
        currentEmployee = employee;
        employeeCard.classList.remove('hidden');
        document.getElementById('employee-initials').textContent = initials(employee.full_name) || '--';
        document.getElementById('employee-name').textContent = employee.full_name;
        document.getElementById('employee-id').textContent = employee.employee_id;
        document.getElementById('employee-role').textContent = employee.role;
        renderTattoos(employee.tattoos);
        renderApprovals(employee.appearance_approvals);
    };

    const prependRecent = (record, isCheck) => {
        document.getElementById('empty-log')?.remove();
        const list = document.getElementById('recent-list');
        const item = document.createElement('div');
        item.className = 'recent-item';
        const status = isCheck ? `<span class="status-pill status-${statusClass(record.status)}">${escapeHtml(record.status)}</span>` : '';
        item.innerHTML = `
            <div class="recent-avatar">${escapeHtml(firstInitial(record.employee_name))}</div>
            <div class="recent-copy"><strong>${escapeHtml(record.employee_name)}</strong><span>${escapeHtml(record.employee_id)} · ${escapeHtml(record.recorded_at)}</span></div>
            ${status}
        `;
        list.prepend(item);
        while (list.children.length > 25) list.lastElementChild.remove();
    };

    const prependHistory = (record, isCheck) => {
        const tableBody = document.getElementById('history-table-body');
        if (!tableBody) return;

        document.getElementById('empty-history')?.remove();
        const row = document.createElement('tr');
        const status = isCheck ? record.status : 'Registered';
        const comments = isCheck && record.comment ? record.comment : '—';

        row.innerHTML = `
            <td class="history-datetime"><strong>${escapeHtml(record.recorded_date)}</strong><span>${escapeHtml(record.recorded_at)}</span></td>
            <td><div class="history-employee"><span class="table-avatar">${escapeHtml(firstInitial(record.employee_name))}</span><div><strong>${escapeHtml(record.employee_name)}</strong><span class="employee-id-inline">ID ${escapeHtml(record.employee_id)}</span></div></div></td>
            <td class="history-role">${escapeHtml(record.role || '—')}</td>
            <td><span class="shift-pill shift-${shiftClass(record.shift)}">${escapeHtml(record.shift || '—')}</span></td>
            <td><span class="status-pill status-${statusClass(status)}">${escapeHtml(status)}</span></td>
            <td class="history-comment">${escapeHtml(comments)}</td>
            <td><span class="recorded-by">${escapeHtml(record.recorded_by || '—')}</span></td>
        `;

        tableBody.prepend(row);
        while (tableBody.children.length > 100) tableBody.lastElementChild.remove();
    };

    const resetCheckSelection = () => {
        selectedStatus = null;
        document.querySelectorAll('.status-btn').forEach(btn => btn.classList.remove('active'));
        if (comment) comment.value = '';
        if (saveCheck) saveCheck.disabled = true;
    };

    scanForm.addEventListener('submit', async (event) => {
        event.preventDefault();
        const employeeId = input.value.trim();
        if (!employeeId) {
            showMessage('Enter an Employee ID.', 'error');
            input.focus();
            return;
        }

        showMessage('Searching HiBob and Appearance data…', 'info');
        try {
            const result = await postJson(shell.dataset.lookupUrl, { employee_id: employeeId });
            renderEmployee(result.employee);
            resetCheckSelection();

            if (process === 'PREPARATION') {
                const saved = await postJson(shell.dataset.preparationUrl, { employee_id: result.employee.employee_id });
                prependRecent(saved.record, false);
                prependHistory(saved.record, false);
                showMessage(`${result.employee.full_name} was registered for Appearance Preparation.`, 'success');
            } else {
                showMessage(`${result.employee.full_name} loaded. Select an Appearance status.`, 'success');
            }
        } catch (error) {
            currentEmployee = null;
            employeeCard.classList.add('hidden');
            showMessage(error.message, 'error');
        } finally {
            input.value = '';
            input.focus();
        }
    });

    document.querySelectorAll('.status-btn').forEach((button) => {
        button.addEventListener('click', () => {
            selectedStatus = button.dataset.status;
            document.querySelectorAll('.status-btn').forEach(btn => btn.classList.remove('active'));
            button.classList.add('active');
            saveCheck.disabled = false;
        });
    });

    saveCheck?.addEventListener('click', async () => {
        if (!currentEmployee || !selectedStatus) return;
        saveCheck.disabled = true;
        try {
            const saved = await postJson(shell.dataset.checkUrl, {
                employee_id: currentEmployee.employee_id,
                status: selectedStatus,
                comment: comment.value.trim(),
            });
            prependRecent(saved.record, true);
            prependHistory(saved.record, true);
            showMessage(`${currentEmployee.full_name} was saved as ${saved.record.status}.`, 'success');
            resetCheckSelection();
            input.focus();
        } catch (error) {
            showMessage(error.message, 'error');
            saveCheck.disabled = false;
        }
    });

    input.focus();
})();
