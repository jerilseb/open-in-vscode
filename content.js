// content.js

const BUTTON_ID_PREFIX = "clone-in-vscode-btn-";
const LISTENER_URL = "http://localhost:45678"; // Make sure this matches your script's port

function getRepoUrl() {
    // GitHub repo URLs are typically window.location.href on the main repo page
    // or can be derived from meta tags for more robustness if needed.
    // For simplicity, we'll use window.location.href.
    // Ensure it's a proper repo URL before sending.
    const currentUrl = window.location.href;
    const githubRepoRegex = /^(https?:\/\/(?:www\.)?github\.com\/[\w.-]+\/[\w.-]+)(?:\/|$)/;
    const match = currentUrl.match(githubRepoRegex);

    if (match && match[1]) {
        // Check if it has a .git suffix, if not, add it for typical clone URLs.
        // Your script might handle this, but it's good practice.
        let repoUrl = match[1];
        if (!repoUrl.endsWith('.git')) {
            repoUrl += '.git';
        }
        return repoUrl;
    }
    return null; // Not a recognized repo page or structure changed
}


async function sendToLocalScript(repoUrl) {
    console.log(`Sending ${repoUrl} to local script at ${LISTENER_URL}`);
    try {
        const response = await fetch(LISTENER_URL, {
            method: 'POST',
            headers: {
                'Content-Type': 'text/plain',
            },
            body: repoUrl
        });

        const responseText = await response.text();
        if (response.ok) {
            console.log('Successfully sent to local script:', responseText);
            // Optionally show a success notification on the page
            // alert(`Clone command sent for: ${repoUrl.split('/').pop().replace('.git','')}\nServer says: ${responseText}`);
        } else {
            console.error('Error sending to local script:', response.status, responseText);
            alert(`Error contacting local script (${response.status}): ${responseText}\nIs your listener script running?`);
        }
    } catch (error) {
        console.error('Fetch error:', error);
        alert(`Failed to connect to python listener at ${LISTENER_URL}.\nIs it running?\nDetails: ${error.message}`);
    }
}

function createCloneButton() {
    const repoUrl = getRepoUrl();
    if (!repoUrl) {
        // console.log("Not on a main GitHub repo page, button not added.");
        return null; // Don't add button if not a clear repo URL
    }

    const buttonId = `${BUTTON_ID_PREFIX}${repoUrl.split('/').slice(-2).join('-').replace('.git','')}`;
    if (document.getElementById(buttonId)) {
        return null; // Button already exists
    }

    const li = document.createElement('li');
    li.id = buttonId + "-li"; // Unique ID for the li element as well

    const divBtnGroup = document.createElement('div');
    divBtnGroup.className = 'BtnGroup'; // Match GitHub's styling
    divBtnGroup.setAttribute('data-view-component', 'true');

    const anchor = document.createElement('a');
    anchor.id = buttonId;
    anchor.href = '#'; // Prevent navigation
    anchor.className = 'btn-sm btn BtnGroup-item'; // Match GitHub's styling
    anchor.setAttribute('data-view-component', 'true');
    anchor.setAttribute('aria-label', 'Clone in VS Code');
    anchor.style.marginLeft = "4px"; // Add a little space from the previous button

    // VS Code Icon SVG
    const svgIcon = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svgIcon.setAttribute('viewBox', '0 0 32 32');
    svgIcon.setAttribute('width', '16');
    svgIcon.setAttribute('height', '16');
    svgIcon.style.verticalAlign = 'text-bottom';
    svgIcon.style.marginRight = '4px';

    // VS Code Icon Path
    const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    path.setAttribute('d', 'M29.821,4.321,24.023,2,11.493,14.212,3.833,8.385l-1.654.837V22.8l1.644.827,7.65-5.827L24.023,30l5.8-2.321V4.321ZM4.65,19.192V12.818L8.2,15.985,4.65,19.192ZM16,15.985l7.082-5.3V21.324l-7.092-5.339H16Z');
    path.setAttribute('fill', '#007acc'); // VS Code blue color

    svgIcon.appendChild(path);
    anchor.appendChild(svgIcon);

    anchor.appendChild(document.createTextNode('Open in VSCode'));

    anchor.addEventListener('click', (event) => {
        event.preventDefault();
        const confirmedRepoUrl = getRepoUrl(); // Re-fetch in case of SPA navigation
        if (confirmedRepoUrl) {
            sendToLocalScript(confirmedRepoUrl);
        } else {
            alert("Could not determine repository URL to clone.");
        }
    });

    divBtnGroup.appendChild(anchor);
    li.appendChild(divBtnGroup);
    return li;
}

function addCloneButtonToPage() {
    const pageheadActions = document.querySelector('ul.pagehead-actions');
    if (pageheadActions) {
        const cloneButtonLi = createCloneButton();
        if (cloneButtonLi && !document.getElementById(cloneButtonLi.id)) { // Check ID of the LI
             // Try to insert it before the "Star" button or at the end
            const starButton = pageheadActions.querySelector('.starring-container'); // This class might change
            if (starButton && starButton.parentElement && starButton.parentElement.tagName === 'LI') {
                pageheadActions.insertBefore(cloneButtonLi, starButton.parentElement);
            } else {
                pageheadActions.appendChild(cloneButtonLi);
            }
            console.log("Clone in VSCode button added.");
        }
    }
}

// GitHub uses Turbo, so content might load dynamically.
// We need to observe for changes and add the button when the target appears.
const observer = new MutationObserver((mutationsList, observer) => {
    for (const mutation of mutationsList) {
        // Check if the 'pagehead-actions' ul is added or its children changed significantly
        if (document.querySelector('ul.pagehead-actions') && !document.querySelector('[id^="' + BUTTON_ID_PREFIX + '"]')) {
            addCloneButtonToPage();
            return; // Add once and stop re-checking for this mutation burst
        }
    }
});

// Start observing the body for childList and subtree modifications
// This is broad, but necessary for dynamic pages like GitHub
observer.observe(document.body, {
    childList: true,
    subtree: true
});

// Initial attempt to add the button on script load
addCloneButtonToPage();