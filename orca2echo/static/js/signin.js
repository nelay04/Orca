document.getElementById('signin-form').addEventListener('submit', function (event) {
  // Prevent multiple form submissions
  var submitButton = document.getElementById('submit-button');
  var overlay = document.getElementById('overlay');

  // Disable the button and show overlay
  submitButton.disabled = true;
  submitButton.classList.add('button-disabled');
  overlay.style.display = 'flex';  // Show overlay

  // Optional: If you need to prevent double submission
  event.preventDefault();  // Prevent default form submission

  // Submit the form manually after a delay to simulate an async process (for demonstration)
  setTimeout(function () {
    document.getElementById('signin-form').submit();  // Submit the form after a short delay
  }, 500);  // Adjust the delay time if necessary
});
