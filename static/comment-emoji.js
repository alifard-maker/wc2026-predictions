(function () {
  function findTextarea(picker) {
    const compose = picker.closest('.comment-compose');
    if (!compose) return null;
    return compose.querySelector('textarea');
  }

  function insertEmoji(textarea, emoji) {
    const max = textarea.maxLength > 0 ? textarea.maxLength : Infinity;
    const start = textarea.selectionStart ?? textarea.value.length;
    const end = textarea.selectionEnd ?? textarea.value.length;
    const next = textarea.value.slice(0, start) + emoji + textarea.value.slice(end);
    if (next.length > max) return;
    textarea.value = next;
    const pos = start + emoji.length;
    textarea.setSelectionRange(pos, pos);
    textarea.focus();
    textarea.dispatchEvent(new Event('input', { bubbles: true }));
  }

  document.addEventListener('click', (e) => {
    const btn = e.target.closest('.emoji-btn');
    if (!btn) return;
    e.preventDefault();
    const picker = btn.closest('.emoji-picker');
    const textarea = picker ? findTextarea(picker) : null;
    if (!textarea) return;
    insertEmoji(textarea, btn.dataset.emoji || btn.textContent.trim());
    btn.classList.add('emoji-btn-pop');
    setTimeout(() => btn.classList.remove('emoji-btn-pop'), 180);
  });
})();
