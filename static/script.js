
// Shared JavaScript across all pages
console.log('E3 Ligase Ligandalyzer loaded');

// Initialize page
document.addEventListener('DOMContentLoaded', () => {
    // Set active nav link based on current page
    const currentPath = window.location.pathname;
    const navLinks = document.querySelectorAll('custom-navbar a');
    
    navLinks.forEach(link => {
        if (link.getAttribute('href') === currentPath) {
            link.classList.add('active');
        } else {
            link.classList.remove('active');
        }
    });

    // Sticky header behavior
    const nav = document.querySelector('custom-navbar').shadowRoot.querySelector('nav');
    if (nav) {
        window.addEventListener('scroll', () => {
            if (window.scrollY > 50) {
                nav.classList.add('scrolled');
            } else {
                nav.classList.remove('scrolled');
            }
        });
    }

    // Initialize feather icons
    if (typeof feather !== 'undefined') {
        feather.replace();
    }
});

// Navigation helper
function navigateTo(page) {
    window.location.href = page;
}
// Show loading overlay
function showLoading(message = 'Loading...') {
    const overlay = document.createElement('div');
    overlay.className = 'loading-overlay';
    overlay.innerHTML = `
        <div class="loading-content loading-float">
            <div class="loading-spinner"></div>
            <p class="text-white font-medium">${message}</p>
        </div>
    `;
    document.body.appendChild(overlay);
    return overlay;
}

// Hide loading overlay
function hideLoading(overlay) {
    if (overlay) {
        overlay.style.opacity = '0';
        setTimeout(() => overlay.remove(), 300);
    }
}

// Example usage:
// const loader = showLoading('Fetching data...');
// await fetchData();
// hideLoading(loader);
// Get color for ligase
function getLigaseColor(ligaseName) {
    const colorMap = {
        'CHIP': 'chip',
        'CRBN': 'crbn',
        'DCAF1': 'dcaf1', 
        'DCAF15': 'dcaf15',
        'DCAF16': 'dcaf16',
        'HUWE1': 'huwe1',
        'KEAP1': 'keap1',
        'MDM2': 'mdm2',
        'NEDD4L': 'nedd4l',
        'PARKIN': 'parkin',
        'RNF4': 'rnf4',
        'RNF8': 'rnf8',
        'RNF43': 'rnf43',
        'SOCS2': 'socs2',
        'TRIM21': 'trim21',
        'VHL': 'vhl',
        'XIAP': 'xiap',
        'cIAP1': 'ciap1',
        'cIAP2': 'ciap2'
    };
    return colorMap[ligaseName] || 'primary';
}
// API endpoints
const ENDPOINTS = {
    FEATURED_RECRUITERS: '/api/featured-recruiters',
    CHEMICAL_DESCRIPTORS: '/api/chemical-descriptors',
    LIGAND_METADATA: '/api/ligand-metadata',
    SCAFFOLD_DATA: '/api/scaffold-data',
    RECRUITERS: '/api/recruiters'
};

// Local data paths
const DATA_BASE = '/Ligases';
const LIGASES = [
    'CHIP', 'CRBN', 'DCAF1', 'DCAF15', 'DCAF16', 'HUWE1', 
    'KEAP1', 'MDM2', 'NEDD4L', 'PARKIN', 'RNF4', 'RNF8',
    'RNF43', 'SOCS2', 'TRIM21', 'VHL', 'XIAP', 'cIAP1', 'cIAP2'
];
// Initialize tooltips
document.addEventListener('DOMContentLoaded', initTooltips);

function initTooltips() {
    const tooltipTriggers = document.querySelectorAll('[data-tooltip]');
    
    tooltipTriggers.forEach(trigger => {
        trigger.addEventListener('mouseenter', showTooltip);
        trigger.addEventListener('mouseleave', hideTooltip);
    });
}

function showTooltip(event) {
    const tooltip = document.createElement('div');
    tooltip.className = 'absolute bg-slate-800 text-white px-3 py-2 rounded text-sm shadow-lg z-50';
    tooltip.textContent = this.getAttribute('data-tooltip');
    tooltip.style.top = `${this.getBoundingClientRect().bottom + window.scrollY}px`;
    tooltip.style.left = `${this.getBoundingClientRect().left + window.scrollX}px`;
    tooltip.id = 'dynamic-tooltip';
    
    document.body.appendChild(tooltip);
}

function hideTooltip() {
    const tooltip = document.getElementById('dynamic-tooltip');
    if (tooltip) tooltip.remove();
}

// Enhanced API functions with error handling and caching
async function fetchLigaseData(ligaseName) {
    try {
        const response = await fetch(`${DATA_BASE}/${ligaseName}/data.json`);
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        
        const data = await response.json();
        if (!data) throw new Error('Invalid data format received');
        
        return data;
    } catch (error) {
        console.error(`Error loading ${ligaseName} data:`, error);
        showNotification(`Failed to load ${ligaseName} data`, 'error');
        return null;
    }
}

async function fetchPDBFile(ligaseName, pdbId) {
    try {
        const response = await fetch(`${DATA_BASE}/${ligaseName}/structures/${pdbId}.pdb`);
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        
        return await response.text();
    } catch (error) {
        console.error(`Error loading PDB file ${pdbId}:`, error);
        return null;
    }
}

async function fetchSDFFile(ligaseName, recruiterCode) {
    try {
        const response = await fetch(`${DATA_BASE}/${ligaseName}/structures/${recruiterCode}.sdf`);
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        
        return await response.text();
    } catch (error) {
        console.error(`Error loading SDF file ${recruiterCode}:`, error);
        return null;
    }
}
// Data fetching functions for specific endpoints
async function fetchData(url, params = {}) {
    try {
        const query = new URLSearchParams(params).toString();
        const response = await fetch(`${url}${query ? `?${query}` : ''}`);
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        return await response.json();
    } catch (error) {
        console.error('Error fetching data:', error);
        showNotification('Failed to fetch data', 'error');
        return null;
    }
}

async function getChemicalDescriptors(recruiterCode) {
    return fetchData(ENDPOINTS.CHEMICAL_DESCRIPTORS, { recruiter_code: recruiterCode });
}

async function getLigandMetadata(ligandName) {
    return fetchData(ENDPOINTS.LIGAND_METADATA, { ligand: ligandName });
}

async function getScaffoldData(ligase) {
    return fetchData(ENDPOINTS.SCAFFOLD_DATA, { ligase });
}

async function getAllRecruiters() {
    return fetchData(ENDPOINTS.RECRUITERS);
}
// UI Helper functions
function disableButtons() {
    document.querySelectorAll('button').forEach(btn => {
        btn.disabled = true;
    });
}

function enableButtons() {
    document.querySelectorAll('button').forEach(btn => {
        btn.disabled = false;
    });
}

function showNotification(message, type = 'info') {
const notification = document.createElement('div');
    notification.className = `fixed top-4 right-4 px-4 py-2 rounded shadow-lg z-50 ${
        type === 'error' ? 'bg-red-500' : 'bg-green-500'
    }`;
    notification.textContent = message;
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.remove();
    }, 5000);
}

// Data processing helpers
function processScaffoldData(data) {
    return data.map(item => ({
        scaffoldId: item.Scaffold_ID,
        recruiterCount: item.Recruiter_Count,
        smiles: item.Scaffold_SMILES,
        murckoSmiles: item.Murcko_SMILES,
        scaffoldClass: item.Scaffold_Class,
        x: parseFloat(item.Scaffold_Center_of_Mass_X),
        y: parseFloat(item.Scaffold_Center_of_Mass_Y),
        z: parseFloat(item.Scaffold_Center_of_Mass_Z),
        connectivity: parseFloat(item.Ligase_Scaffold_Connectivity),
        recruiterDensity: parseFloat(item.Recruiter_Density_Score),
        shannonIndex: parseFloat(item.Shannon_Diversity_Index)
    }));
}

function processChemicalDescriptors(data) {
    return data.map(item => ({
        recruiterCode: item.RECRUITER_CODE,
        mw: parseFloat(item.MW),
        logP: parseFloat(item.LogP),
        tpsa: parseFloat(item.TPSA),
        hba: parseInt(item.HBA),
        hbd: parseInt(item.HBD),
        rotatableBonds: parseInt(item.Rotatable_Bonds),
        qed: parseFloat(item.QED),
        saScore: parseFloat(item.SA_Score),
        lipinskiPass: item.Lipinski_Pass === 'True',
        smiles: item.SMILES,
        painsHits: parseInt(item.PAINS_Hits)
    }));
}
