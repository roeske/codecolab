/** 
 * Triggers an alert if a jQuery selector matches nothing.
 *
 * This should only be used for cases where the selector
 * must match for the code to be valid. There are cases
 * where it is OK for the selector to not match, as well.
 */
function require(selector) {
    if ($(selector).length === 0) {
        alert("Selector: " + selector + " matched no elements.");
    } 

    return selector;
}
