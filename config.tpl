<p>Change configuration of S0-Logger:</p>

<form action="{{path}}/config" method="GET">
    <label for="energy">Energy [Wh]:
        <input type="text" size="10" name="energy" value="{{energy}}">

    </label>

    <p>
    <fieldset>
        <legend> Debug </legend>  
        <input type="radio" id="true" name="debug" value="True" {{"checked" if debug else ""}}>
        <label for="true"> enabled</label>
        <input type="radio" id="false" name="debug" value="False" {{"" if debug else "checked"}}>
        <label for="false"> disabled</label>
    </fieldset>
    </label>
    </p>

    <p>
    <fieldset>
        <legend> Simulation </legend>
        <input type="radio" id="true" name="simulate" value="True" {{"checked" if simulate else ""}}>
        <label for="true"> enabled</label>
        <input type="radio" id="false" name="simulate" value="False" {{"" if simulate else "checked"}}>
        <label for="false"> disabled</label>
    </fieldset>
    </p>
    <input type="submit" name="save" value="save">
</form>
