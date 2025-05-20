const passwordInput = document.getElementById('password-input');
const strengthBar = document.getElementById('password-strength-bar');
const strengthText = document.getElementById('password-strength-text');

passwordInput.addEventListener('input', () => {
    const value = passwordInput.value;
    let strength = 0;
    if (value.length >= 8) strength++;
    if (/[A-Z]/.test(value)) strength++;
    if (/[a-z]/.test(value)) strength++;
    if (/\d/.test(value)) strength++;
    if (/[\W_]/.test(value)) strength++;

    const barClasses = ['bg-danger', 'bg-warning', 'bg-primary', 'bg-primary', 'bg-success'];
    const textClasses = ['text-danger', 'text-warning', 'text-primary', 'text-primary', 'text-success'];
    const levels = ['Muito fraca', 'Fraca', 'Razoável', 'Forte', 'Muito forte'];

    // Reset bar
    strengthBar.className = 'h-100 rounded transition-all';
    strengthBar.classList.add(barClasses[strength - 1] || 'bg-secondary');
    strengthBar.style.width = `${(strength / 5) * 100}%`;

    // Reset text on zero
    if (strength === 0) {
        strengthText.textContent = strengthText.getAttribute('data-old-text') || '';
        strengthText.className = strengthText.getAttribute('data-old-class') || '';
        return;
    }

    // Update strength text
    strengthText.setAttribute('data-old-text', strengthText.textContent);
    strengthText.textContent = levels[strength - 1];
    strengthText.className = 'fs-7 mt-1 ' + (textClasses[strength - 1] || 'text-muted');
});