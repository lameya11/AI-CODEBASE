import '@testing-library/jest-dom'

// Mock scrollIntoView which is not available in jsdom
window.HTMLElement.prototype.scrollIntoView = function() {}
