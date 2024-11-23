function openSidebar() {
    const sidebar = document.getElementById("mySidebar");
    const overlay = document.getElementById("overlay");

    sidebar.style.width = "300px";
    sidebar.classList.add("open");
    overlay.classList.add("active");
}

function closeSidebar() {
    const sidebar = document.getElementById("mySidebar");
    const overlay = document.getElementById("overlay");

    sidebar.style.width = "0";
    sidebar.classList.remove("open");
    overlay.classList.remove("active");
}

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
