/** Project View */

function cc_make_card_editable(project_name, elem, card_id) {
    var id = card_id

    $(elem).find(".editable.text").editable("/project/" + project_name + "/cards/edit/" + id, {
        name: "text",
        event: "click",
        style: "inherit",
        onblur: "submit",
        tooltip: "Click to edit...",
        width: $(elem).width() + 80 + "px",

        callback: function(value, settings) {
            console.log("settings=" + settings)
            console.log("value=" + value)

            // Must update the card in the list (not modal) when the modal
            // is changed so they do not come out of sync with each other.
            $("li[data-id=" + card_id + "].card_item").find("p span.text").text(value)
        }
    })

    $(elem).find(".editable.description").editable("/project/" + project_name + "/cards/edit/" + id, {
        onblur: "submit",
        name: "description",
        event: "click",
        style: "inherit",
        tooltip: "Click to edit...",
        cancel: "Cancel",
        submit: "Save",
        type: "textarea",
        width: "400px",
        height: "100px",
    })
}


/** 
 * Post the updates to the "/cards/reorder" API 
 *
 * @param updates -- [{  _id: <int>, pile_id: <int>, number: <int> }, ...]
 * */
function cc_cards_reorder_post(updates) {
    $.ajax({
        type: "POST",
        url: "/cards/reorder", 
        data: JSON.stringify({updates: updates}),
        
        success: function(data) {
            console.log(JSON.stringify(data))
        },

        contentType: "application/json;charset=UTF-8"
    })
}


/** 
 * Updates the DOM after cards are reordered. Returns array of
 * update values appropriate for posting back to the server via
 * cc_cards_reorder_post(updates)
 *
 * @param children -- Function returning the list items that need
 *                    to be updated.
 */
function cc_cards_reorder_update_dom(children) {
    // Now, update the pile id of the card in the database, too.
    var updates = []

    // Iterate the children and obtain the data-number values:
    var sort_numbers = []
    
    children().each(function(i, elem) {
        sort_numbers.push($(elem).data("number"))
    })
    
    // Sort the data number values least to greatest.
    var sorted_numbers = sort_numbers.sort(function(a,b) {
        return a - b
    })

    // Re-iterate the existing children and write the numbers back
    // in order, while pushing updates onto the updates array.
    children().each(function(i, elem) {
        var number = sorted_numbers[i]

        // Need to update it in the DOM & on the server.
        $(elem).data("number", number)
        
        updates.push({
            _id: $(elem).data("id"),
            number: $(elem).data("number"),
            pile_id: $(elem).data("pile-id")
        })
    })
  
    return updates;
}

/** 
 * Factory for "sortable" objects. Used to make a card sortable in jQueryUI.
 */
function cc_make_sortable(selector) {
    var children = function() { 
        return $(selector + " li.card_item").not("li.ui-sortable-placeholder") 
    }
    
    var indexes_to_sort_keys =  {}

    var that = {
        delay: 100,
        distance: 10,
        revert: "invalid",
        connectWith: "ul.card_list",
        tolerance: "pointer",
        placeholder: "empty_card",
        containment: "window",

        receive: function(event, ui) {
            console.log("receive")

            // Update the pile id of the card, because we just
            // dropped it into a pile.
            $(ui.item).data("pile-id", $(this).data("id"))
  
            // Update the values in the DOM to reflect the current
            // state of the cards.
            var updates = cc_cards_reorder_update_dom(children)
            
            // Post those updates back to the server.
            cc_cards_reorder_post(updates)
        },


        stop: function(event, ui) {
            console.log("stop")
           
            // Update the values in the DOM to reflect the current
            // state of the cards.
            var updates = cc_cards_reorder_update_dom(children)
            
            // Post those updates back to the server.
            cc_cards_reorder_post(updates)
        }
    }

    return that
}


/** 
 * Makes fields classed with the 'editable' class editable, and submit
 * changes to backend when the user presses 'enter'.
 */
function cc_setup_editable_fields(project_name) {
    var selector = ".editable.pile_title"

    // Make pile names editable
    $(selector).each(function(i, elem) {
        var id = $(elem).attr("data-id")
        $(elem).editable("/project/" + project_name + "/piles/edit/" + id, {
            event: "click",
            style: "inherit",
            onblur: "submit",
            width: $(elem).width() + 20 + "px"
        })
    })
}


function cc_connect_card_to_modal(project_name, elem) {
    // Create id to later reference modal with.
    var modal_id = "modal_" + $(elem).attr("data-id")

    var url = "/project/" + project_name + "/cards/" + $(elem).attr("data-id")

    var options = {
        title: "Edit Card",
        autoOpen: false,
        width: 500,
        height: 300
    }

    var modal = $("<div id=" + modal_id + "></div>").load(url).dialog(options)

    console.log("elem=" + elem)

    // Make it pop up a modal.
    $(elem).dblclick(function() {
        console.log("url="+ url)
        modal.dialog("open")
        return false
    })
}


/**
 * Sets up all state of the project page.
 */
function cc_project_init(project_name, pile_ids) {
    // Iterate pile ids and make sortable + droppable.
    for (var key in pile_ids) {
        id = pile_ids[key]
        // Build selector.
        var selector = "#" + id
        // Make the target list sortable.
        $(selector).sortable(cc_make_sortable(selector)).disableSelection()
    }

    $("li.card_item").each(function(i, elem) {
        $(elem).attr("data-project-name", project_name)
        cc_connect_card_to_modal(project_name, elem)
    })

    $("ul, li").disableSelection()
    
    cc_setup_editable_fields(project_name)
}
