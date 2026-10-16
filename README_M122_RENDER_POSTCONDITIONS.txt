M122 Render Postconditions

Validate the returned backend result and reserved output file before marking export completed. Invalid results are recorded as failed, with cleanup of the incomplete output. Regression tests cover unsuccessful results, missing or empty files, unexpected paths, and preservation of existing exports.
