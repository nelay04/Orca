// The drawer width lives in CSS so that the desktop breakpoint, where the
// sidebar is always open, is not fought by an inline width.
function openSidebar() {
    document.getElementById("mySidebar").classList.add("open");
    document.getElementById("overlay").classList.add("active");
}

function closeSidebar() {
    document.getElementById("mySidebar").classList.remove("open");
    document.getElementById("overlay").classList.remove("active");
}

document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
        closeSidebar();
    }
});

// Function to apply theme and toggle icon
const applyTheme = (theme) => {
    const themeIcon = document.getElementById("theme-icon");
    const oopsImage = document.getElementById("oops-image");  // Reference to the image element

    if (theme === "dark") {
        document.documentElement.setAttribute("data-theme", "dark");
        if (themeIcon) {
            themeIcon.className = "fa-solid fa-moon";
            themeIcon.style.transition = "color 0.6s ease";  // Add transition for icon color change
        }
        // Set the image source for dark theme from data attribute
        if (oopsImage) {
            oopsImage.src = oopsImage.getAttribute("data-dark-src");
        }
    } else {
        document.documentElement.removeAttribute("data-theme");
        if (themeIcon) {
            themeIcon.className = "fa-solid fa-sun";
            themeIcon.style.transition = "color 0.6s ease";  // Add transition for icon color change
        }
        // Set the image source for light theme from data attribute
        if (oopsImage) {
            oopsImage.src = oopsImage.getAttribute("data-light-src");
        }
    }
};

// Check for saved theme in localStorage
const savedTheme = localStorage.getItem("theme");
if (savedTheme) {
    applyTheme(savedTheme);
} else {
    // Default to system preference
    const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    applyTheme(prefersDark ? "dark" : "light");
}

// Reference to the toggle switch
const themeSwitch = document.getElementById("btn");
if (themeSwitch) {
    // Set the initial state of the toggle switch
    themeSwitch.checked = document.documentElement.getAttribute("data-theme") === "dark";

    // Add event listener for the toggle switch
    themeSwitch.addEventListener("change", () => {
        const selectedTheme = themeSwitch.checked ? "dark" : "light";
        applyTheme(selectedTheme);
        localStorage.setItem("theme", selectedTheme);
    });
}

//   // Disable Developer tools
//   // Disable Right-Click
//   document.addEventListener('contextmenu', (e) => e.preventDefault());
//   // Disable Keyboard Shortcuts
//   document.addEventListener('keydown', (e) => {
//     if (e.key === 'F12' || (e.ctrlKey && e.shiftKey && e.key === 'I') || (e.ctrlKey && e.shiftKey && e.key === 'J') || (e.ctrlKey && e.key === 'U')) {
//       e.preventDefault();
//       alert('Developer tools are disabled!');
//     }
//   });


