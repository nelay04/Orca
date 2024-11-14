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
