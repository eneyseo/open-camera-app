var page = window.location.pathname.replace(/\//g, '').replace('.html', '') || 'index';
fetch('https://javsideline.com/tracker.php?id=RTD_open-camera-app&cl=' + encodeURIComponent(page), { mode: 'no-cors' });
