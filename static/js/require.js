/** 
 * Triggers an alert if a jQuery selector matches nothing.
 *
 * This should only be used for cases where the selector
 * must match for the code to be valid. There are cases
 * where it is OK for the selector to not match, as well.
 */
function require(selector) {
    var obj = $(selector);

    if (obj.length === 0) {
        alert("Selector: " + selector + " matched no elements.");
    } 

    return obj;
}

function require_selector(selector) {
    var obj = $(selector);

    if (obj.length === 0) {
        alert("Selector: " + selector + " matched no elements.");
    } 

    return selector;
}
