(() => {
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
