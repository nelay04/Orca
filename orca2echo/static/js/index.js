// Get the search input and search icon elements
const searchInput = document.getElementById("searchInput");
const searchIcon = document.getElementById("searchIcon");

// Toggle search input visibility on search icon click
searchIcon.addEventListener("click", function() {
    if (searchInput.style.width === "200px") {
        searchInput.style.width = "0";  // Collapse the input field
        searchInput.style.opacity = "0"; // Make it disappear
    } else {
        searchInput.style.width = "200px";  // Expand the input field
        searchInput.style.opacity = "1";    // Make it visible
    }
});
