
const inputField = document.getElementById('email')
const icon = document.querySelector('.icon')

inputField.addEventListener('focus', () => {
  icon.style.top = '20%' // Move icon to top on focus
})

inputField.addEventListener('blur', () => {
  if (inputField.value.trim() === '') {
    icon.style.top = '50%' // Reset icon to initial position if input is blank
  }
})