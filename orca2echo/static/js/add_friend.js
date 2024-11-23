
const inputField = document.getElementById('short_names')
const icon = document.querySelector('.icon')

inputField.addEventListener('focus', () => {
  icon.style.top = '20%' // Move icon to top on focus
})

const inputField_two = document.getElementById('id_number')
const icon_two = document.querySelector('.icon')

inputField_two.addEventListener('focus', () => {
  icon_two.style.top = '20%' // Move icon to top on focus
})



inputField.addEventListener('blur', () => {
  if (inputField.value.trim() === '') {
    icon.style.top = '50%' // Reset icon to initial position if input is blank
  }
})

document.getElementById('add-friend-form').addEventListener('submit', function (event) {
  // Prevent multiple form submissions
  var submitButton = document.getElementById('submit-button');
  var overlay = document.getElementById('overlay_form');

  // Disable the button and show overlay
  submitButton.disabled = true;
  submitButton.classList.add('button-disabled');
  overlay.style.display = 'flex';  // Show overlay

  // Optional: If you need to prevent double submission
  event.preventDefault();  // Prevent default form submission

  // Submit the form manually after a delay to simulate an async process (for demonstration)
  setTimeout(function () {
    document.getElementById('add-friend-form').submit();  // Submit the form after a short delay
  }, 500);  // Adjust the delay time if necessary
});
