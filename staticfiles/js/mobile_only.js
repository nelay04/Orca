// Check screen width to identify mobile switch using dev tool
// Allowing bypass
if (window.innerWidth < 1024) { // Assuming screen widths greater than 1024px are desktops
    window.location.href = "/"; // Redirect to index
  }  

function goBack() {
    window.close();
}