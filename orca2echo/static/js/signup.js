// Select necessary elements
const form = document.getElementById('signup-form');
const submitButton = document.getElementById('submit-button');
const overlay = document.getElementById('overlay');

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
