window.addEventListener('scroll', () => {
    const navbar = document.getElementById('navbar');
    if (window.scrollY > 0) {
        navbar.classList.add('scrolled');
    } else {
        navbar.classList.remove('scrolled');
    }
});


function submitForm(username) {
    const form = document.getElementById('form-' + username);  // Ensure form ID is correct
    if (form) {
        form.submit();
    } else {
        console.error('Form not found for user ID: ' + username);
    }
}
