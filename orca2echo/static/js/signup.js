// Select necessary elements
const inputField = document.getElementById('email');
const icon = document.querySelector('.icon');
const form = document.getElementById('signin-form');
const submitButton = document.getElementById('submit-button');
const overlay = document.getElementById('overlay');

// Adjust icon position on input field focus/blur
if (inputField && icon) {
  inputField.addEventListener('focus', () => {
    icon.style.top = '20%'; // Move icon to top on focus
  });

  inputField.addEventListener('blur', () => {
    if (inputField.value.trim() === '') {
      icon.style.top = '50%'; // Reset icon to initial position if input is blank
    }
  });
}

// Prevent multiple submissions and manage overlay display
if (form && submitButton && overlay) {
  form.addEventListener('submit', function (event) {
    // Prevent default form submission to handle custom logic
    event.preventDefault();

    // Disable the button to prevent multiple submissions
    submitButton.disabled = true;
    submitButton.classList.add('button-disabled');
    overlay.style.display = 'flex';  // Display overlay to indicate loading

    // Simulate form processing (adjust the delay or remove if not needed)
    setTimeout(() => {
      form.submit();  // Programmatically submit the form after a short delay
    }, 500);  // Adjust delay time if necessary
  });
}
