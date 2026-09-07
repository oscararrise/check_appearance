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
    const escapeHtml = (value) => String(value).replace(/[&<>'"]/g, (char) => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]));

    const renderEmployee = (employee) => {
        currentEmployee = employee;
        employeeCard.classList.remove('hidden');
        document.getElementById('employee-initials').textContent = initials(employee.full_name) || '--';
        document.getElementById('employee-name').textContent = employee.full_name;
        document.getElementById('employee-id').textContent = employee.employee_id;
        document.getElementById('employee-role').textContent = employee.role;

        const summary = document.getElementById('tattoo-summary');
        const records = document.getElementById('tattoo-records');
        records.innerHTML = '';

        if (!employee.tattoos.has_record) {
            summary.className = 'tattoo-summary unknown';
            summary.textContent = 'No active tattoo record was found for this Employee ID.';
        } else if (employee.tattoos.cover_required) {
            summary.className = 'tattoo-summary cover';
            summary.textContent = 'Tattoo record found — coverage is required.';
        } else {
            summary.className = 'tattoo-summary clear';
            summary.textContent = 'Tattoo record found — coverage is not required.';
        }

        employee.tattoos.records.forEach((item) => {
            const el = document.createElement('div');
            el.className = 'tattoo-item';
            const cover = item.should_be_covered === true ? 'Yes' : item.should_be_covered === false ? 'No' : 'Not specified';
            el.innerHTML = `<strong>Cover required: ${cover}</strong><p>${escapeHtml(item.details || 'Tattoo record')}</p><p>Location: ${escapeHtml(item.location || 'Not specified')}</p>${item.connotation ? `<p>Connotation: ${escapeHtml(item.connotation)}</p>` : ''}`;
            records.appendChild(el);
        });
    };

    const prependRecent = (record, isCheck) => {
        document.getElementById('empty-log')?.remove();
        const list = document.getElementById('recent-list');
        const item = document.createElement('div');
        item.className = 'recent-item';
        const status = isCheck ? `<span class="status-pill status-${record.status.toLowerCase().replaceAll(' ', '_')}">${escapeHtml(record.status)}</span>` : '';
        item.innerHTML = `<div><strong>${escapeHtml(record.employee_name)}</strong><span>${escapeHtml(record.employee_id)} · ${escapeHtml(record.recorded_at)}</span></div>${status}`;
        list.prepend(item);
        while (list.children.length > 25) list.lastElementChild.remove();
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

        showMessage('Searching HiBob…', 'info');
        try {
            const result = await postJson(shell.dataset.lookupUrl, { employee_id: employeeId });
            renderEmployee(result.employee);
            resetCheckSelection();

            if (process === 'PREPARATION') {
                const saved = await postJson(shell.dataset.preparationUrl, { employee_id: result.employee.employee_id });
                prependRecent(saved.record, false);
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
