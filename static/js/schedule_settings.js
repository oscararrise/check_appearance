(() => {
    const cards = [...document.querySelectorAll('.schedule-settings-card')];
    if (!cards.length) return;

    const csrfToken = () => {
        const name = 'csrftoken=';
        const cookie = document.cookie.split(';').map(value => value.trim()).find(value => value.startsWith(name));
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
        if (!response.ok) throw new Error(data.error || 'Unable to save schedule.');
        return data;
    };

    cards.forEach((card) => {
        const saveButton = card.querySelector('.settings-save-button');
        const status = card.querySelector('.settings-save-status');
        const process = card.dataset.process;

        const showStatus = (text, type = '') => {
            status.textContent = text;
            status.className = `settings-save-status ${type}`.trim();
        };

        saveButton.addEventListener('click', async () => {
            const schedule = [...card.querySelectorAll('.settings-shift-row')].map((row) => ({
                shift: row.dataset.shift,
                start_time: row.querySelector('.settings-start').value,
                end_time: row.querySelector('.settings-end').value,
            }));

            if (schedule.some(item => !item.start_time || !item.end_time)) {
                showStatus('Complete every start and end time before saving.', 'error');
                return;
            }

            saveButton.disabled = true;
            showStatus('Saving schedule…');

            try {
                const result = await postJson(card.dataset.updateUrl, { schedule });
                result.schedule.forEach((item) => {
                    const row = card.querySelector(`[data-shift="${item.shift}"]`);
                    if (!row) return;
                    row.querySelector('.settings-start').value = item.start_time;
                    row.querySelector('.settings-end').value = item.end_time;
                });
                showStatus(`✓ ${process === 'PREPARATION' ? 'Preparation' : 'Check'} schedule saved`, 'success');
            } catch (error) {
                showStatus(error.message, 'error');
            } finally {
                saveButton.disabled = false;
            }
        });
    });
})();
