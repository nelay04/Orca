// Handling OTP input fields
const otpInputs = document.querySelectorAll('.otp_input');
const otpHiddenInput = document.getElementById('otp');

otpInputs.forEach((input, index) => {
  // Handle input event to move focus and update the hidden input
  input.addEventListener('input', () => {
    if (input.value.length === 1 && index < otpInputs.length - 1) {
      otpInputs[index + 1].focus();
    }
    // Collect values and assign to hidden input
    otpHiddenInput.value = Array.from(otpInputs).map(input => input.value).join('');
  });

  // Handle backspace key to move focus backwards
  input.addEventListener('keydown', (e) => {
    if (e.key === "Backspace" && index > 0 && input.value === "") {
      otpInputs[index - 1].focus();
    }
  });

  // Handle paste event (when OTP is pasted)
  input.addEventListener('paste', (e) => {
    const pastedData = e.clipboardData.getData('text').slice(0, otpInputs.length); // Limit paste to OTP length
    otpInputs.forEach((input, index) => {
      input.value = pastedData[index] || ''; // Fill OTP fields with pasted data
    });
    otpHiddenInput.value = pastedData; // Update hidden input
  });
});

// Form submission with overlay and disabled button
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



// Initialize the timer
let timer = 15;

// Function to update the timer every second
const countdown = setInterval(function () {
  timer--;
  document.getElementById('timer').textContent = timer;

  // Update message and show the "Resend" link after the timer completes
  if (timer <= 0) {
    clearInterval(countdown);
    document.getElementById('otpMessage').style.display = 'none'; // Hide the initial message
    document.getElementById('resendMessage').style.display = 'block'; // Show the "Resend" message with the link
    document.getElementById('refreshLink').style.pointerEvents = 'auto'; // Enable the "Resend" link
    document.getElementById('refreshLink').style.color = 'white'; // Change color to indicate it's enabled
  }
}, 1000); // Update every 1000 milliseconds (1 second)

// Prevent page refresh using F5 or Ctrl+R (desktop)
window.addEventListener('beforeunload', function (event) {
  if (timer > 0) {
    event.preventDefault(); // Prevent the refresh
    event.returnValue = ''; // Show confirmation dialog
  }
});

// Disable manual page refresh by intercepting keypresses (like F5, Ctrl+R)
window.addEventListener('keydown', function (event) {
  if ((event.key === 'F5') || (event.ctrlKey && event.key === 'r')) {
    event.preventDefault(); // Prevent page refresh
  }
});

// Disable right-click menu (Context menu) on the page to prevent refresh
window.addEventListener('contextmenu', function (event) {
  if (timer > 0) {
    event.preventDefault(); // Prevent right-click
  }
});

// Prevent swipe-down refresh on mobile devices (touch devices)
let touchStartY = 0;
let touchEndY = 0;

window.addEventListener('touchstart', function (event) {
  touchStartY = event.touches[0].clientY;
});

window.addEventListener('touchend', function (event) {
  touchEndY = event.changedTouches[0].clientY;

  // Check for swipe down (used for refresh on mobile browsers)
  if (touchStartY < touchEndY && timer > 0) {
    event.preventDefault(); // Prevent refresh swipe gesture
  }
});

// Disable "Resend" link initially and allow it only after timer is completed
let isResendAllowed = false;

// "Resend" link click event
document.getElementById('refreshLink').addEventListener('click', function (event) {
  if (isResendAllowed) {
    // Prevent multiple clicks by disabling the link again
    event.preventDefault();
    event.stopImmediatePropagation();

    // Disable further clicks and change the color to indicate it's been clicked
    document.getElementById('refreshLink').style.pointerEvents = 'none';
    document.getElementById('refreshLink').style.color = 'gray';

    // Perform the refresh or action here
    window.location.reload(); // Or any other action you'd like to perform
  }
});

// Enable clicking after each timer reset (if you have another timer, reset isResendAllowed to true)
function resetResend() {
  isResendAllowed = true;
  document.getElementById('refreshLink').style.pointerEvents = 'auto'; // Enable the "Resend" link
  document.getElementById('refreshLink').style.color = 'white'; // Change color to indicate it's enabled
}
