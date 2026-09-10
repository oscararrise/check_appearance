(() => {
    const clockMarkup = `
        <div class="colombia-clock" data-colombia-clock aria-label="Current date and time in Colombia">
            <span class="clock-live-dot" aria-hidden="true"></span>
            <span class="clock-date" data-clock-date>Colombia date</span>
            <span class="clock-divider" aria-hidden="true"></span>
            <span class="clock-time" data-clock-time>--:--</span>
            <span class="clock-zone">COL</span>
        </div>`;

    document.querySelectorAll('.topbar-actions').forEach((actions) => {
        if (!actions.querySelector('[data-colombia-clock]')) {
            actions.insertAdjacentHTML('afterbegin', clockMarkup);
        }
    });

    const clocks = document.querySelectorAll('[data-colombia-clock]');
    if (!clocks.length) return;

    const timeZone = 'America/Bogota';
    const dateFormatter = new Intl.DateTimeFormat('en-US', {
        timeZone,
        weekday: 'short',
        month: 'short',
        day: '2-digit',
        year: 'numeric',
    });
    const timeFormatter = new Intl.DateTimeFormat('en-GB', {
        timeZone,
        hour: '2-digit',
        minute: '2-digit',
        hour12: false,
    });

    const updateClock = () => {
        const now = new Date();
        const dateText = dateFormatter.format(now);
        const timeText = timeFormatter.format(now);

        clocks.forEach((clock) => {
            const dateTarget = clock.querySelector('[data-clock-date]');
            const timeTarget = clock.querySelector('[data-clock-time]');
            if (dateTarget) dateTarget.textContent = dateText;
            if (timeTarget) timeTarget.textContent = timeText;
            clock.setAttribute('title', `${dateText} · ${timeText} Colombia time`);
        });
    };

    updateClock();
    window.setInterval(updateClock, 30000);
})();