document.querySelectorAll('button[data-toggle-password="true"]').forEach(btn => {
  // encontra o input password/text dentro do mesmo container
  const container = btn.parentElement;
  const input = container.querySelector('input[type="password"], input[type="text"]');
  const iconShow = btn.querySelector('.ki-eye');
  const iconHide = btn.querySelector('.ki-eye-slash');

  btn.addEventListener('click', () => {
    if (input.type === 'password') {
      input.type = 'text';
      iconShow.classList.add('hidden');
      iconHide.classList.remove('hidden');
    } else {
      input.type = 'password';
      iconShow.classList.remove('hidden');
      iconHide.classList.add('hidden');
    }
  });
});