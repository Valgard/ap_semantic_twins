<?php

namespace Shipping;

// Deliberately separate from Ordering\CustomerDto: the shipping context must not
// be coupled to the ordering schema. See the anti-corruption layer decision.
final class CustomerDto
{
    public static function fromRow(array $row): self
    {
        $dto = new self();
        $dto->id = $row['customer_id'];
        $dto->name = $row['display_name'];
        return $dto;
    }
}
