
// const inputField = document.getElementById('short_names')
// const icon = document.querySelector('.icon')

// inputField.addEventListener('focus', () => {
//   icon.style.top = '20%' // Move icon to top on focus
// })

// const inputField_two = document.getElementById('id_number')
// const icon_two = document.querySelector('.icon')

// inputField_two.addEventListener('focus', () => {
//   icon_two.style.top = '20%' // Move icon to top on focus
// })



// inputField.addEventListener('blur', () => {
//   if (inputField.value.trim() === '') {
//     icon.style.top = '50%' // Reset icon to initial position if input is blank
//   }
// })

document.getElementById('add-friend-form').addEventListener('submit', function (event) {
  event.preventDefault(); // Prevent default form submission

  // var submitButton = document.getElementById('submit-button');
  // var overlay = document.getElementById('overlay_form');

  // // Disable the button and show overlay
  // submitButton.disabled = true;
  // submitButton.classList.add('button-disabled');
  // overlay.style.display = 'flex';

  // Get form values
  var shortName = document.getElementById('short_name').value;
  var idNumber = document.getElementById('id_number').value;

  // First Base64 encoding (URL-safe)
  function base64UrlEncode(value) {
    return btoa(value).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
  }

  // Second Base64 encoding (double encode, URL-safe)
  function doubleBase64UrlEncode(value) {
    return base64UrlEncode(base64UrlEncode(value));
  }

  var doubleEncodedShortName = doubleBase64UrlEncode(shortName);
  var doubleEncodedIdNumber = doubleBase64UrlEncode(idNumber);

  // Create encoded URL
  var encodedUrl = `/search-profile?short-name=${encodeURIComponent(doubleEncodedShortName)}&id-number=${encodeURIComponent(doubleEncodedIdNumber)}`;

  // Redirect to the encoded URL
  window.location.href = encodedUrl;
});

